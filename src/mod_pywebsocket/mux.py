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


"""This file provides classes and helper functions for multiplexing extension.

Specification:
http://tools.ietf.org/html/draft-ietf-hybi-websocket-multiplexing-01
"""


import email
import email.parser
import logging
import math
import struct

from mod_pywebsocket import common
from mod_pywebsocket import util
from mod_pywebsocket._stream_base import ConnectionTerminatedException
from mod_pywebsocket._stream_hybi import Frame
from mod_pywebsocket._stream_hybi import create_binary_frame
from mod_pywebsocket._stream_hybi import parse_frame


_CONTROL_CHANNEL_ID = 0
_DEFAULT_CHANNEL_ID = 1

_MUX_OPCODE_ADD_CHANNEL_REQUEST = 0
_MUX_OPCODE_ADD_CHANNEL_RESPONSE = 1
_MUX_OPCODE_FLOW_CONTROL = 2
_MUX_OPCODE_DROP_CHANNEL = 3
_MUX_OPCODE_ENCAPSULATED_CONTROL_FRAME = 4

_MAX_CHANNEL_ID = 2 ** 29 - 1


class MuxUnexpectedException(Exception):
    """Exception in handling multiplexing extension."""
    pass


# Temporary
class MuxNotImplementedException(Exception):
    """Raised when a flow enters unimplemented code path."""
    pass


class InvalidMuxFrameException(Exception):
    """Raised when an invalid multiplexed frame received."""
    pass


class InvalidMuxControlBlockException(Exception):
    """Raised when an invalid multiplexing control block received."""
    pass


def _encode_channel_id(channel_id):
    if channel_id < 0:
        raise ValueError('Channel id %d must not be negative' % channel_id)

    if channel_id < 2 ** 7:
        return chr(channel_id)
    if channel_id < 2 ** 14:
        return struct.pack('!H', 0x8000 + channel_id)
    if channel_id < 2 ** 21:
        first = chr(0xc0 + (channel_id >> 16))
        return first + struct.pack('!H', channel_id & 0xffff)
    if channel_id < 2 ** 29:
        return struct.pack('!L', 0xe0000000 + channel_id)

    raise ValueError('Channel id %d is too large' % channel_id)


def _create_control_block_length_value(channel_id, opcode, flags, value):
    """Creates a control block that consists of objective channel id, opcode,
    flags, encoded length of opcode specific value, and the value.
    Most of control blocks have this structure.

    Args:
        channel_id: objective channel id.
        opcode: opcode of the control block.
        flags: 3bit opcode specific flags.
        value: opcode specific data.
    """

    if channel_id < 0 or channel_id > _MAX_CHANNEL_ID:
        raise ValueError('Invalid channel id: %d' % channel_id)
    if opcode < 0 or opcode > _MUX_OPCODE_ENCAPSULATED_CONTROL_FRAME:
        raise ValueError('Invalid opcode: %d' % opcode)
    if flags < 0 or flags > 7:
        raise ValueError('Invalid flags: %x' % flags)
    length = len(value)
    if length < 0 or length > 2 ** 32 - 1:
        raise ValueError('Invalid length: %d' % length)

    # The first byte comes after the objective channel id consists of
    # opcode, opcode specific flags, and size of the size of value in bytes
    # minus 1.
    if length > 0:
        # Calculate the minimum number of bits that are required to store the
        # value of length.
        bits_of_length = int(math.floor(math.log(length, 2)))
        first_byte = (opcode << 5) | (flags << 2) | (bits_of_length / 8)
    else:
        first_byte = (opcode << 5) | (flags << 2) | 0

    encoded_length = ''
    if length < 2 ** 8:
        encoded_length = chr(length)
    elif length < 2 ** 16:
        encoded_length = struct.pack('!H', length)
    elif length < 2 ** 24:
        encoded_length = chr(length >> 16) + struct.pack('!H',
                                                         length & 0xffff)
    else:
        encoded_length = struct.pack('!L', length)

    return (_encode_channel_id(channel_id) + chr(first_byte) +
            encoded_length + value)


def _create_add_channel_response(channel_id, encoded_handshake,
                                 encoding=0, rejected=False):
    if encoding != 0 and encoding != 1:
        raise ValueError('Invalid encoding %d' % encoding)

    flags = (rejected << 2) | encoding
    block = _create_control_block_length_value(
                channel_id, _MUX_OPCODE_ADD_CHANNEL_RESPONSE,
                flags, encoded_handshake)
    payload = _encode_channel_id(_CONTROL_CHANNEL_ID) + block
    return create_binary_frame(payload, mask=False)


def _create_drop_channel(channel_id, reason='', mux_error=False):
    if not mux_error and len(reason) > 0:
        raise ValueError('Reason must be empty if mux_error is False')

    flags = mux_error << 2
    block = _create_control_block_length_value(
                channel_id, _MUX_OPCODE_DROP_CHANNEL,
                flags, reason)
    payload = _encode_channel_id(_CONTROL_CHANNEL_ID) + block
    return create_binary_frame(payload, mask=False)


def _create_encapsulated_control_frame(objective_channel_id, inner_frame):
    payload = (_encode_channel_id(_CONTROL_CHANNEL_ID) +
               _encode_channel_id(objective_channel_id) +
               chr(_MUX_OPCODE_ENCAPSULATED_CONTROL_FRAME << 5) +
               inner_frame)
    return create_binary_frame(payload, mask=False)


def _parse_request_text(request_text):
    request_line, header_lines = request_text.split('\r\n', 1)

    words = request_line.split(' ')
    if len(words) != 3:
        raise ValueError('Bad Request-Line syntax %r' % request_line)
    [command, path, version] = words
    if version != 'HTTP/1.1':
        raise ValueError('Bad request version %r' % version)

    # email.parser.Parser() parses RFC 2822 (RFC 822) style headers.
    # RFC 6455 refers RFC 2616 for handshake parsing, and RFC 2616 refers
    # RFC 822.
    headers = email.parser.Parser().parsestr(header_lines)
    return command, path, version, headers


class _ControlBlock(object):
    """A structure that holds parsing result of multiplexing control block.
    Control block specific attributes will be added by _MuxFramePayloadParser.
    (e.g. encoded_handshake will be added for AddChannelRequest and
    AddChannelResponse)
    """

    def __init__(self, opcode, channel_id):
        self.opcode = opcode
        self.channel_id = channel_id


class _MuxFramePayloadParser(object):
    """A class that parses multiplexed frame payload."""

    def __init__(self, payload):
        self._data = payload
        self._read_position = 0
        self._logger = util.get_class_logger(self)

    def read_channel_id(self):
        """Reads channel id.

        Raises:
            InvalidMuxFrameException: when the payload doesn't contain
                valid channel id.
        """

        remaining_length = len(self._data) - self._read_position
        pos = self._read_position
        if remaining_length == 0:
            raise InvalidMuxFrameException('No channel id found')

        channel_id = ord(self._data[pos])
        channel_id_length = 1
        if channel_id & 0xe0 == 0xe0:
            if remaining_length < 4:
                raise InvalidMuxFrameException(
                    'Invalid channel id format')
            channel_id = struct.unpack('!L',
                                       self._data[pos:pos+4])[0] & 0x1fffffff
            channel_id_length = 4
        elif channel_id & 0xc0 == 0xc0:
            if remaining_length < 3:
                raise InvalidMuxFrameException(
                    'Invalid channel id format')
            channel_id = (((channel_id & 0x1f) << 16) +
                          struct.unpack('!H', self._data[pos+1:pos+3])[0])
            channel_id_length = 3
        elif channel_id & 0x80 == 0x80:
            if remaining_length < 2:
                raise InvalidMuxFrameException(
                    'Invalid channel id format')
            channel_id = struct.unpack('!H',
                                       self._data[pos:pos+2])[0] & 0x3fff
            channel_id_length = 2
        self._read_position += channel_id_length

        return channel_id

    def _read_opcode_specific_data(self, opcode, size_of_size):
        """Reads opcode specific data that consists of followings:
            - the size of the opcode specific data (1-4 bytes)
            - the opcode specific data
        AddChannelRequest and DropChannel have this structure.
        """

        if self._read_position + size_of_size > len(self._data):
            raise InvalidMuxControlBlockException(
                'No size field for opcode %d' % opcode)

        pos = self._read_position
        size = 0
        if size_of_size == 1:
            size = ord(self._data[pos])
            pos += 1
        elif size_of_size == 2:
            size = struct.unpack('!H', self._data[pos:pos+2])[0]
            pos += 2
        elif size_of_size == 3:
            size = ord(self._data[pos]) << 16
            size += struct.unpack('!H', self._data[pos+1:pos+3])[0]
            pos += 3
        elif size_of_size == 4:
            size = struct.unpack('!L', self._data[pos:pos+4])[0]
            pos += 4
        else:
            raise InvalidMuxControlBlockException(
                'Invalid size of the size field for opcode %d' % opcode)

        if pos + size > len(self._data):
            raise InvalidMuxControlBlockException(
                'No data field for opcode %d (%d + %d > %d)' %
                (opcode, pos, size, len(self._data)))

        specific_data = self._data[pos:pos+size]
        self._read_position = pos + size
        return specific_data

    def _read_add_channel_request(self, first_byte, control_block):
        reserved = (first_byte >> 4) & 0x1
        encoding = (first_byte >> 2) & 0x3
        size_of_handshake_size = (first_byte & 0x3) + 1

        encoded_handshake = self._read_opcode_specific_data(
                                _MUX_OPCODE_ADD_CHANNEL_REQUEST,
                                size_of_handshake_size)
        control_block.encoding = encoding
        control_block.encoded_handshake = encoded_handshake
        return control_block

    def _read_flow_control(self, first_byte, control_block):
        # TODO(bashi): Implement
        raise MuxNotImplementedException('FlowControl is not implemented')

    def _read_drop_channel(self, first_byte, control_block):
        mux_error = (first_byte >> 4) & 0x1
        reserved = (first_byte >> 2) & 0x3
        size_of_reason_size = (first_byte & 0x3) + 1

        reason = self._read_opcode_specific_data(
                     _MUX_OPCODE_ADD_CHANNEL_RESPONSE,
                     size_of_reason_size)
        if mux_error and len(reason) > 0:
            raise InvalidMuxControlBlockException(
                'Reason must be empty when F bit is set')
        control_block.mux_error = mux_error
        control_block.reason = reason
        return control_block

    def _read_encapsulated_control_frame(self, first_byte, control_block):
        def _receive_bytes(length):
            if self._read_position + length > len(self._data):
                raise ConnectionTerminatedException(
                    'Incomplete encapsulated control frame received.')
            data = self._data[self._read_position:self._read_position+length]
            self._read_position += length
            return data

        try:
            opcode, payload, fin, rsv1, rsv2, rsv3 = (
                parse_frame(_receive_bytes, self._logger,
                            unmask_receive=False))
        except ConnectionTerminatedException, e:
            raise InvalidMuxControlBlockException(e)

        if not fin:
            raise InvalidMuxControlBlockException(
                'Encapsulated control frames must not be fragmented')
        if not common.is_control_opcode(opcode):
            raise InvalidMuxControlBlockException(
                'Opcode %d is not a control opcode' % opcode)

        control_block.frame = Frame(fin=fin, rsv1=rsv1, rsv2=rsv2, rsv3=rsv3,
                                    opcode=opcode, payload=payload)
        return control_block

    def read_control_blocks(self):
        """Reads control block(s).

        Raises:
           InvalidMuxControlBlock: when the payload contains invalid control
               block(s).
           StopIteration: when no control blocks left.
        """

        while self._read_position < len(self._data):
            objective_channel_id = self.read_channel_id()
            if self._read_position >= len(self._data):
                raise InvalidMuxControlBlockException(
                    'No control opcode found')
            first_byte = ord(self._data[self._read_position])
            self._read_position += 1
            opcode = (first_byte >> 5) & 0x7
            control_block = _ControlBlock(opcode=opcode,
                                          channel_id=objective_channel_id)
            if opcode == _MUX_OPCODE_ADD_CHANNEL_REQUEST:
                yield self._read_add_channel_request(first_byte, control_block)
            elif opcode == _MUX_OPCODE_FLOW_CONTROL:
                yield self._read_flow_control(first_byte, control_block)
            elif opcode == _MUX_OPCODE_DROP_CHANNEL:
                yield self._read_drop_channel(first_byte, control_block)
            elif opcode == _MUX_OPCODE_ENCAPSULATED_CONTROL_FRAME:
                yield self._read_encapsulated_control_frame(first_byte,
                                                            control_block)
            else:
                raise InvalidMuxControlBlockException(
                    'Invalid opcode %d' % opcode)
        assert self._read_position == len(self._data)
        raise StopIteration

    def remaining_data(self):
        """Returns remaining data."""

        return self._data[self._read_position:]


# vi:sts=4 sw=4 et
