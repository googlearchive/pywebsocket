#!/usr/bin/env python
#
# Copyright 2012, Google Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


"""Tests for mux module."""

import Queue
import logging
import optparse
import unittest
import struct
import sys

import set_sys_path  # Update sys.path to locate mod_pywebsocket module.

from mod_pywebsocket import common
from mod_pywebsocket import mux
from mod_pywebsocket._stream_hybi import create_binary_frame


def _create_request_header(path='/echo'):
    return (
        'GET %s HTTP/1.1\r\n'
        'Host: server.example.com\r\n'
        'Upgrade: websocket\r\n'
        'Connection: Upgrade\r\n'
        'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n'
        'Sec-WebSocket-Version: 13\r\n'
        'Origin: http://example.com\r\n'
        '\r\n') % path


class MuxTest(unittest.TestCase):
    """A unittest for mux module."""

    def test_channel_id_decode(self):
        data = '\x00\x01\xbf\xff\xdf\xff\xff\xff\xff\xff\xff'
        parser = mux._MuxFramePayloadParser(data)
        channel_id = parser.read_channel_id()
        self.assertEqual(0, channel_id)
        channel_id = parser.read_channel_id()
        self.assertEqual(1, channel_id)
        channel_id = parser.read_channel_id()
        self.assertEqual(2 ** 14 - 1, channel_id)
        channel_id = parser.read_channel_id()
        self.assertEqual(2 ** 21 - 1, channel_id)
        channel_id = parser.read_channel_id()
        self.assertEqual(2 ** 29 - 1, channel_id)
        self.assertEqual(len(data), parser._read_position)

    def test_channel_id_encode(self):
        encoded = mux._encode_channel_id(0)
        self.assertEqual('\x00', encoded)
        encoded = mux._encode_channel_id(2 ** 14 - 1)
        self.assertEqual('\xbf\xff', encoded)
        encoded = mux._encode_channel_id(2 ** 14)
        self.assertEqual('\xc0@\x00', encoded)
        encoded = mux._encode_channel_id(2 ** 21 - 1)
        self.assertEqual('\xdf\xff\xff', encoded)
        encoded = mux._encode_channel_id(2 ** 21)
        self.assertEqual('\xe0 \x00\x00', encoded)
        encoded = mux._encode_channel_id(2 ** 29 - 1)
        self.assertEqual('\xff\xff\xff\xff', encoded)
        # channel_id is too large
        self.assertRaises(ValueError,
                          mux._encode_channel_id,
                          2 ** 29)

    def test_create_control_block_length_value(self):
        data = 'Hello, world!'
        block = mux._create_control_block_length_value(
            channel_id=1, opcode=mux._MUX_OPCODE_ADD_CHANNEL_REQUEST,
            flags=0x7, value=data)
        expected = '\x01\x1c\x0dHello, world!'
        self.assertEqual(expected, block)

        data = 'a' * (2 ** 8)
        block = mux._create_control_block_length_value(
            channel_id=2, opcode=mux._MUX_OPCODE_ADD_CHANNEL_RESPONSE,
            flags=0x0, value=data)
        expected = '\x02\x21\x01\x00' + data
        self.assertEqual(expected, block)

        data = 'b' * (2 ** 16)
        block = mux._create_control_block_length_value(
            channel_id=3, opcode=mux._MUX_OPCODE_DROP_CHANNEL,
            flags=0x0, value=data)
        expected = '\x03\x62\x01\x00\x00' + data
        self.assertEqual(expected, block)

    def test_read_control_blocks(self):
        data = ('\x01\x00\00'
                '\x02\x61\x01\x00%s'
                '\x03\x0a\x01\x00\x00%s'
                '\x04\x63\x01\x00\x00\x00%s') % (
            'a' * 0x0100, 'b' * 0x010000, 'c' * 0x01000000)
        parser = mux._MuxFramePayloadParser(data)
        blocks = list(parser.read_control_blocks())
        self.assertEqual(4, len(blocks))

        self.assertEqual(mux._MUX_OPCODE_ADD_CHANNEL_REQUEST, blocks[0].opcode)
        self.assertEqual(0, blocks[0].encoding)
        self.assertEqual(0, len(blocks[0].encoded_handshake))

        self.assertEqual(mux._MUX_OPCODE_DROP_CHANNEL, blocks[1].opcode)
        self.assertEqual(0, blocks[1].mux_error)
        self.assertEqual(0x0100, len(blocks[1].reason))

        self.assertEqual(mux._MUX_OPCODE_ADD_CHANNEL_REQUEST, blocks[2].opcode)
        self.assertEqual(2, blocks[2].encoding)
        self.assertEqual(0x010000, len(blocks[2].encoded_handshake))

        self.assertEqual(mux._MUX_OPCODE_DROP_CHANNEL, blocks[3].opcode)
        self.assertEqual(0, blocks[3].mux_error)
        self.assertEqual(0x01000000, len(blocks[3].reason))

        self.assertEqual(len(data), parser._read_position)

    def test_read_encapsulated_control_frame(self):
        data = '\x01\x80\x88\x06FooBar'
        parser = mux._MuxFramePayloadParser(data)
        blocks = list(parser.read_control_blocks())
        self.assertEqual(1, len(blocks))
        self.assertEqual(1, blocks[0].channel_id)
        self.assertEqual(common.OPCODE_CLOSE, blocks[0].frame.opcode)
        self.assertEqual(1, blocks[0].frame.fin)
        self.assertEqual('FooBar', blocks[0].frame.payload)

        # fin is not set
        data = '\x01\x80\x08\x06FooBar'
        parser = mux._MuxFramePayloadParser(data)
        # Use lambda: list(...) because parser.read_control_blocks() returns
        # a generator and it doesn't throw exceptions until it is used
        self.assertRaises(mux.InvalidMuxControlBlockException,
                          lambda: list(parser.read_control_blocks()))

        # opcode is not a control opcode
        data = '\x01\x80\x80\x06FooBar'
        parser = mux._MuxFramePayloadParser(data)
        self.assertRaises(mux.InvalidMuxControlBlockException,
                          lambda: list(parser.read_control_blocks()))

    def test_create_add_channel_response(self):
        data = mux._create_add_channel_response(channel_id=1,
                                                encoded_handshake='FooBar',
                                                encoding=0,
                                                rejected=False)
        self.assertEqual('\x82\x0a\x00\x01\x20\x06FooBar', data)

        data = mux._create_add_channel_response(channel_id=2,
                                                encoded_handshake='Hello',
                                                encoding=1,
                                                rejected=True)
        self.assertEqual('\x82\x09\x00\x02\x34\x05Hello', data)

    def test_drop_channel(self):
        data = mux._create_drop_channel(channel_id=1,
                                        reason='',
                                        mux_error=False)
        self.assertEqual('\x82\x04\x00\x01\x60\x00', data)

        data = mux._create_drop_channel(channel_id=1,
                                        reason='error',
                                        mux_error=True)
        self.assertEqual('\x82\x09\x00\x01\x70\x05error', data)

        # reason must be empty if mux_error is False.
        self.assertRaises(ValueError,
                          mux._create_drop_channel,
                          1, 'FooBar', False)

    def test_create_encapsulated_control_frame(self):
        inner_frame = create_binary_frame(
            message="FooBar", fin=1, opcode=common.OPCODE_CLOSE)
        data = mux._create_encapsulated_control_frame(
            objective_channel_id=1, inner_frame=inner_frame)
        self.assertEqual('\x82\x0b\x00\x01\x80\x88\x06FooBar', data)

    def test_parse_request_text(self):
        request_text = _create_request_header()
        command, path, version, headers = mux._parse_request_text(request_text)
        self.assertEqual('GET', command)
        self.assertEqual('/echo', path)
        self.assertEqual('HTTP/1.1', version)
        self.assertEqual(6, len(headers))
        self.assertEqual('server.example.com', headers['Host'])
        self.assertEqual('websocket', headers['Upgrade'])
        self.assertEqual('Upgrade', headers['Connection'])
        self.assertEqual('dGhlIHNhbXBsZSBub25jZQ==',
                         headers['Sec-WebSocket-Key'])
        self.assertEqual('13', headers['Sec-WebSocket-Version'])
        self.assertEqual('http://example.com', headers['Origin'])


if __name__ == '__main__':
    unittest.main()

# vi:sts=4 sw=4 et
