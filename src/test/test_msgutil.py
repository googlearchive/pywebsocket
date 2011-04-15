#!/usr/bin/env python
#
# Copyright 2011, Google Inc.
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


"""Tests for msgutil module."""


import array
import Queue
import struct
import unittest

import set_sys_path  # Update sys.path to locate mod_pywebsocket module.

from mod_pywebsocket import common
from mod_pywebsocket import msgutil
from mod_pywebsocket.stream import Stream
from mod_pywebsocket.stream import StreamHixie75
from mod_pywebsocket import util
from test import mock


# We use one fixed nonce for testing instead of cryptographically secure PRNG.
_MASKING_NONCE = 'ABCD'


def _mask_hybi06(frame):
    frame_key = map(ord, _MASKING_NONCE)
    frame_key_len = len(frame_key)
    result = array.array('B')
    result.fromstring(frame)
    count = 0
    for i in xrange(len(result)):
        result[i] ^= frame_key[count]
        count = (count + 1) % frame_key_len
    return _MASKING_NONCE + result.tostring()


# We'll get data given as read_data on calling request.connection.read().
def _create_request(*frames):
    read_data = []
    for frame in frames:
        read_data.append(_mask_hybi06(frame))

    req = mock.MockRequest(connection=mock.MockConn(''.join(read_data)))
    req.ws_version = common.VERSION_HYBI06
    req.ws_stream = Stream(req)
    return req


# Data written to this request can be read out by calling
# request.connection.written_data()
def _create_blocking_request():
    req = mock.MockRequest(connection=mock.MockBlockingConn())
    req.ws_version = common.VERSION_HYBI06
    req.ws_stream = Stream(req)
    return req


def _create_request_hixie75(read_data):
    req = mock.MockRequest(connection=mock.MockConn(read_data))
    req.ws_stream = StreamHixie75(req)
    return req


def _create_blocking_request_hixie75():
    req = mock.MockRequest(connection=mock.MockBlockingConn())
    req.ws_stream = StreamHixie75(req)
    return req


# TODO(tyoshino): Add deflate test.
class MessageTest(unittest.TestCase):
    # Tests for Stream
    def test_send_message(self):
        request = _create_request('')
        msgutil.send_message(request, 'Hello')
        self.assertEqual('\x84\x05Hello', request.connection.written_data())

        payload = 'a' * 125
        request = _create_request('')
        msgutil.send_message(request, payload)
        self.assertEqual('\x84\x7d' + payload,
                         request.connection.written_data())

    def test_send_medium_message(self):
        payload = 'a' * 126
        request = _create_request('')
        msgutil.send_message(request, payload)
        self.assertEqual('\x84\x7e\x00\x7e' + payload,
                         request.connection.written_data())

        payload = 'a' * ((1 << 16) - 1)
        request = _create_request('')
        msgutil.send_message(request, payload)
        self.assertEqual('\x84\x7e\xff\xff' + payload,
                         request.connection.written_data())

    def test_send_large_message(self):
        payload = 'a' * (1 << 16)
        request = _create_request('')
        msgutil.send_message(request, payload)
        self.assertEqual('\x84\x7f\x00\x00\x00\x00\x00\x01\x00\x00' + payload,
                         request.connection.written_data())

    def test_send_message_unicode(self):
        request = _create_request('')
        msgutil.send_message(request, u'\u65e5')
        # U+65e5 is encoded as e6,97,a5 in UTF-8
        self.assertEqual('\x84\x03\xe6\x97\xa5',
                         request.connection.written_data())

    def test_send_message_fragments(self):
        request = _create_request('')
        msgutil.send_message(request, 'Hello', False)
        msgutil.send_message(request, ' ', False)
        msgutil.send_message(request, 'World', False)
        msgutil.send_message(request, '!', True)
        self.assertEqual('\x04\x05Hello\x00\x01 \x00\x05World\x80\x01!',
                         request.connection.written_data())

    def test_send_fragments_immediate_zero_termination(self):
        request = _create_request('')
        msgutil.send_message(request, 'Hello World!', False)
        msgutil.send_message(request, '', True)
        self.assertEqual('\x04\x0cHello World!\x80\x00',
                         request.connection.written_data())

    def test_receive_message(self):
        request = _create_request('\x84\x05Hello', '\x84\x06World!')
        self.assertEqual('Hello', msgutil.receive_message(request))
        self.assertEqual('World!', msgutil.receive_message(request))

        payload = 'a' * 125
        request = _create_request('\x84\x7d' + payload)
        self.assertEqual(payload, msgutil.receive_message(request))

    def test_receive_medium_message(self):
        payload = 'a' * 126
        request = _create_request('\x84\x7e\x00\x7e' + payload)
        self.assertEqual(payload, msgutil.receive_message(request))

        payload = 'a' * ((1 << 16) - 1)
        request = _create_request('\x84\x7e\xff\xff' + payload)
        self.assertEqual(payload, msgutil.receive_message(request))

    def test_receive_large_message(self):
        payload = 'a' * (1 << 16)
        request = _create_request(
            '\x84\x7f\x00\x00\x00\x00\x00\x01\x00\x00' + payload)
        self.assertEqual(payload, msgutil.receive_message(request))

    def test_receive_message_unicode(self):
        request = _create_request('\x84\x03\xe6\x9c\xac')
        # U+672c is encoded as e6,9c,ac in UTF-8
        self.assertEqual(u'\u672c', msgutil.receive_message(request))

    def test_receive_message_erroneous_unicode(self):
        # \x80 and \x81 are invalid as UTF-8.
        request = _create_request('\x84\x02\x80\x81')
        # Invalid characters should be replaced with
        # U+fffd REPLACEMENT CHARACTER
        self.assertEqual(u'\ufffd\ufffd', msgutil.receive_message(request))

    def test_receive_fragments(self):
        request = _create_request(
            '\x04\x05Hello', '\x00\x01 ', '\x00\x05World', '\x80\x01!')
        self.assertEqual('Hello World!', msgutil.receive_message(request))

    def test_receive_fragments_unicode(self):
        # UTF-8 encodes U+6f22 into e6bca2 and U+5b57 into e5ad97.
        request = _create_request(
            '\x04\x02\xe6\xbc', '\x00\x02\xa2\xe5', '\x80\x02\xad\x97')
        self.assertEqual(u'\u6f22\u5b57', msgutil.receive_message(request))

    def test_receive_fragments_immediate_zero_termination(self):
        request = _create_request(
            '\x04\x0cHello World!', '\x80\x00')
        self.assertEqual('Hello World!', msgutil.receive_message(request))

    def test_receive_fragments_duplicate_start(self):
        request = _create_request(
            '\x04\x05Hello', '\x04\x05World')
        self.assertRaises(msgutil.InvalidFrameException,
                          msgutil.receive_message,
                          request)

    def test_receive_fragments_intermediate_but_not_started(self):
        request = _create_request('\x00\x05Hello')
        self.assertRaises(msgutil.InvalidFrameException,
                          msgutil.receive_message,
                          request)

    def test_receive_fragments_end_but_not_started(self):
        request = _create_request('\x80\x05Hello')
        self.assertRaises(msgutil.InvalidFrameException,
                          msgutil.receive_message,
                          request)

    def test_receive_message_discard(self):
        request = _create_request(
            '\x85\x06IGNORE', '\x84\x05Hello',
            '\x85\x09DISREGARD', '\x84\x06World!')
        self.assertRaises(msgutil.UnsupportedFrameException,
                          msgutil.receive_message, request)
        self.assertEqual('Hello', msgutil.receive_message(request))
        self.assertRaises(msgutil.UnsupportedFrameException,
                          msgutil.receive_message, request)
        self.assertEqual('World!', msgutil.receive_message(request))

    def test_receive_close(self):
        request = _create_request(
            '\x81\x0a' + struct.pack('!H', 1000) + 'Good bye')
        self.assertEqual(None, msgutil.receive_message(request))
        self.assertEqual(1000, request.ws_close_code)
        self.assertEqual('Good bye', request.ws_close_reason)

    def test_send_ping(self):
        request = _create_request('')
        msgutil.send_ping(request, 'Hello World!')
        self.assertEqual('\x82\x0cHello World!',
                         request.connection.written_data())

    def test_receive_ping(self):
        def handler(request, message):
            request.called = True

        # Stream automatically respond to ping with pong without any action
        # by application layer.
        request = _create_request(
            '\x82\x05Hello', '\x84\x05World')
        self.assertEqual('World', msgutil.receive_message(request))
        self.assertEqual('\x83\x05Hello',
                         request.connection.written_data())

        request = _create_request(
            '\x82\x05Hello', '\x84\x05World')
        request.on_ping_handler = handler
        self.assertEqual('World', msgutil.receive_message(request))
        self.assertTrue(request.called)

    def test_receive_pong(self):
        def handler(request, message):
            request.called = True

        request = _create_request(
            '\x83\x05Hello', '\x84\x05World')
        request.on_pong_handler = handler
        msgutil.send_ping(request, 'Hello')
        self.assertEqual('\x82\x05Hello',
                         request.connection.written_data())
        # Valid pong is received, but receive_message won't return for it.
        self.assertEqual('World', msgutil.receive_message(request))
        self.assertEqual('\x82\x05Hello',
                         request.connection.written_data())

        self.assertTrue(request.called)

    def test_receive_extra_or_bad_pong(self):
        # No preceding ping.
        request = _create_request(
            '\x83\x05Hello', '\x84\x05World')
        self.assertRaises(msgutil.InvalidFrameException,
                          msgutil.receive_message,
                          request)

        request = _create_request(
            '\x83\x05Hello', '\x84\x05World')
        msgutil.send_ping(request, 'Jumbo')
        # Body mismatch.
        self.assertRaises(msgutil.InvalidFrameException,
                          msgutil.receive_message,
                          request)

    def test_ping_cannot_be_fragmented(self):
        request = _create_request('\x02\x05Hello')
        self.assertRaises(msgutil.InvalidFrameException,
                          msgutil.receive_message,
                          request)

    def test_ping_with_too_long_payload(self):
        request = _create_request('\x82\x7e\x01\x00' + 'a' * 256)
        self.assertRaises(msgutil.InvalidFrameException,
                          msgutil.receive_message,
                          request)


class MessageTestHixie75(unittest.TestCase):
    # Tests for StreamHixie75
    def test_send_message(self):
        request = _create_request_hixie75('')
        msgutil.send_message(request, 'Hello')
        self.assertEqual('\x00Hello\xff', request.connection.written_data())

    def test_send_message_unicode(self):
        request = _create_request_hixie75('')
        msgutil.send_message(request, u'\u65e5')
        # U+65e5 is encoded as e6,97,a5 in UTF-8
        self.assertEqual('\x00\xe6\x97\xa5\xff',
                         request.connection.written_data())

    def test_receive_message(self):
        request = _create_request_hixie75('\x00Hello\xff\x00World!\xff')
        self.assertEqual('Hello', msgutil.receive_message(request))
        self.assertEqual('World!', msgutil.receive_message(request))

    def test_receive_message_unicode(self):
        request = _create_request_hixie75('\x00\xe6\x9c\xac\xff')
        # U+672c is encoded as e6,9c,ac in UTF-8
        self.assertEqual(u'\u672c', msgutil.receive_message(request))

    def test_receive_message_erroneous_unicode(self):
        # \x80 and \x81 are invalid as UTF-8.
        request = _create_request_hixie75('\x00\x80\x81\xff')
        # Invalid characters should be replaced with
        # U+fffd REPLACEMENT CHARACTER
        self.assertEqual(u'\ufffd\ufffd', msgutil.receive_message(request))

    def test_receive_message_discard(self):
        request = _create_request_hixie75('\x80\x06IGNORE\x00Hello\xff'
                                '\x01DISREGARD\xff\x00World!\xff')
        self.assertEqual('Hello', msgutil.receive_message(request))
        self.assertEqual('World!', msgutil.receive_message(request))


class MessageReceiverTest(unittest.TestCase):
    def test_queue(self):
        request = _create_blocking_request()
        receiver = msgutil.MessageReceiver(request)

        self.assertEqual(None, receiver.receive_nowait())

        request.connection.put_bytes(_mask_hybi06('\x84\x06Hello!'))
        self.assertEqual('Hello!', receiver.receive())

    def test_onmessage(self):
        onmessage_queue = Queue.Queue()
        def onmessage_handler(message):
            onmessage_queue.put(message)

        request = _create_blocking_request()
        receiver = msgutil.MessageReceiver(request, onmessage_handler)

        request.connection.put_bytes(_mask_hybi06('\x84\x06Hello!'))
        self.assertEqual('Hello!', onmessage_queue.get())


class MessageReceiverHixie75Test(unittest.TestCase):
    def test_queue(self):
        request = _create_blocking_request_hixie75()
        receiver = msgutil.MessageReceiver(request)

        self.assertEqual(None, receiver.receive_nowait())

        request.connection.put_bytes('\x00Hello!\xff')
        self.assertEqual('Hello!', receiver.receive())

    def test_onmessage(self):
        onmessage_queue = Queue.Queue()
        def onmessage_handler(message):
            onmessage_queue.put(message)

        request = _create_blocking_request_hixie75()
        receiver = msgutil.MessageReceiver(request, onmessage_handler)

        request.connection.put_bytes('\x00Hello!\xff')
        self.assertEqual('Hello!', onmessage_queue.get())


class MessageSenderTest(unittest.TestCase):
    def test_send(self):
        request = _create_blocking_request()
        sender = msgutil.MessageSender(request)

        sender.send('World')
        self.assertEqual('\x84\x05World', request.connection.written_data())

    def test_send_nowait(self):
        # Use a queue to check the bytes written by MessageSender.
        # request.connection.written_data() cannot be used here because
        # MessageSender runs in a separate thread.
        send_queue = Queue.Queue()
        def write(bytes):
            send_queue.put(bytes)
        request = _create_blocking_request()
        request.connection.write = write

        sender = msgutil.MessageSender(request)

        sender.send_nowait('Hello')
        sender.send_nowait('World')
        self.assertEqual('\x84\x05Hello', send_queue.get())
        self.assertEqual('\x84\x05World', send_queue.get())


class MessageSenderHixie75Test(unittest.TestCase):
    def test_send(self):
        request = _create_blocking_request_hixie75()
        sender = msgutil.MessageSender(request)

        sender.send('World')
        self.assertEqual('\x00World\xff', request.connection.written_data())

    def test_send_nowait(self):
        # Use a queue to check the bytes written by MessageSender.
        # request.connection.written_data() cannot be used here because
        # MessageSender runs in a separate thread.
        send_queue = Queue.Queue()
        def write(bytes):
            send_queue.put(bytes)
        request = _create_blocking_request_hixie75()
        request.connection.write = write

        sender = msgutil.MessageSender(request)

        sender.send_nowait('Hello')
        sender.send_nowait('World')
        self.assertEqual('\x00Hello\xff', send_queue.get())
        self.assertEqual('\x00World\xff', send_queue.get())


if __name__ == '__main__':
    unittest.main()


# vi:sts=4 sw=4 et
