#!/usr/bin/env python
#
# Copyright 2009, Google Inc.
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


import Queue
import unittest

import config  # This must be imported before mod_pywebsocket.
from mod_pywebsocket import msgutil
from mod_pywebsocket import stream
from mod_pywebsocket import stream_hixie75

import mock


def _create_request(read_data):
    req = mock.MockRequest(connection=mock.MockConn(read_data))
    req.ws_stream = stream.Stream(req)
    return req


def _create_blocking_request():
    req = mock.MockRequest(connection=mock.MockBlockingConn())
    req.ws_stream = stream.Stream(req)
    return req


def _create_request_hixie75(read_data):
    req = mock.MockRequest(connection=mock.MockConn(read_data))
    req.ws_stream = stream_hixie75.StreamHixie75(req)
    return req


def _create_blocking_request_hixie75():
    req = mock.MockRequest(connection=mock.MockBlockingConn())
    req.ws_stream = stream_hixie75.StreamHixie75(req)
    return req


class MessageTest(unittest.TestCase):
    def test_send_message(self):
        request = _create_request('')
        msgutil.send_message(request, 'Hello')
        self.assertEqual('\x04\x05Hello', request.connection.written_data())

        payload = 'a' * 125
        request = _create_request('')
        msgutil.send_message(request, payload)
        self.assertEqual('\x04\x7d' + payload,
                         request.connection.written_data())

    def test_send_medium_message(self):
        payload = 'a' * 126
        request = _create_request('')
        msgutil.send_message(request, payload)
        self.assertEqual('\x04\x7e\x00\x7e' + payload,
                         request.connection.written_data())

        payload = 'a' * ((1 << 16) - 1)
        request = _create_request('')
        msgutil.send_message(request, payload)
        self.assertEqual('\x04\x7e\xff\xff' + payload,
                         request.connection.written_data())

    def test_send_large_message(self):
        payload = 'a' * (1 << 16)
        request = _create_request('')
        msgutil.send_message(request, payload)
        self.assertEqual('\x04\x7f\x00\x00\x00\x00\x00\x01\x00\x00' + payload,
                         request.connection.written_data())

    def test_send_message_unicode(self):
        request = _create_request('')
        msgutil.send_message(request, u'\u65e5')
        # U+65e5 is encoded as e6,97,a5 in UTF-8
        self.assertEqual('\x04\x03\xe6\x97\xa5',
                         request.connection.written_data())

    def test_receive_message(self):
        request = _create_request('\x04\x05Hello\x04\x06World!')
        self.assertEqual('Hello', msgutil.receive_message(request))
        self.assertEqual('World!', msgutil.receive_message(request))

        payload = 'a' * 125
        request = _create_request('\x04\x7d' + payload)
        self.assertEqual(payload, msgutil.receive_message(request))

    def test_receive_medium_message(self):
        payload = 'a' * 126
        request = _create_request('\x04\x7e\x00\x7e' + payload)
        self.assertEqual(payload, msgutil.receive_message(request))

        payload = 'a' * ((1 << 16) - 1)
        request = _create_request('\x04\x7e\xff\xff' + payload)
        self.assertEqual(payload, msgutil.receive_message(request))

    def test_receive_large_message(self):
        payload = 'a' * (1 << 16)
        request = _create_request('\x04\x7f\x00\x00\x00\x00\x00\x01\x00\x00'
                                  + payload)
        self.assertEqual(payload, msgutil.receive_message(request))

    def test_receive_message_unicode(self):
        request = _create_request('\x04\x03\xe6\x9c\xac')
        # U+672c is encoded as e6,9c,ac in UTF-8
        self.assertEqual(u'\u672c', msgutil.receive_message(request))

    def test_receive_message_erroneous_unicode(self):
        # \x80 and \x81 are invalid as UTF-8.
        request = _create_request('\x04\x02\x80\x81')
        # Invalid characters should be replaced with
        # U+fffd REPLACEMENT CHARACTER
        self.assertEqual(u'\ufffd\ufffd', msgutil.receive_message(request))

    def test_receive_message_discard(self):
        request = _create_request('\x05\x06IGNORE\x04\x05Hello'
                                  '\x05\x09DISREGARD\x04\x06World!')
        self.assertEqual('Hello', msgutil.receive_message(request))
        self.assertEqual('World!', msgutil.receive_message(request))


class MessageTestHixie75(unittest.TestCase):
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

    def test_payload_length(self):
        for length, bytes in ((0, '\x00'), (0x7f, '\x7f'), (0x80, '\x81\x00'),
                              (0x1234, '\x80\xa4\x34')):
            self.assertEqual(
                length,
                msgutil._payload_length(_create_request_hixie75(bytes)))

    def test_create_header(self):
        # more, rsv1, ..., rsv4 are all true
        header = msgutil.create_header(msgutil.OPCODE_TEXT, 1, 1, 1, 1, 1, 1)
        self.assertEqual('\xf4\x81', header)

        # Maximum payload size
        header = msgutil.create_header(
            msgutil.OPCODE_TEXT, (1 << 63) - 1, 0, 0, 0, 0, 0)
        self.assertEqual('\x04\x7f\x7f\xff\xff\xff\xff\xff\xff\xff', header)

        # Invalid opcode 0x10
        self.assertRaises(Exception,
                          msgutil.create_header,
                          0x10, 0, 0, 0, 0, 0, 0)

        # Invalid value 0xf passed to more parameter
        self.assertRaises(Exception,
                          msgutil.create_header,
                          msgutil.OPCODE_TEXT, 0, 0xf, 0, 0, 0, 0)

        # Too long payload_length
        self.assertRaises(Exception,
                          msgutil.create_header,
                          msgutil.OPCODE_TEXT, 1 << 63, 0, 0, 0, 0, 0)



class MessageReceiverTest(unittest.TestCase):
    def test_queue(self):
        request = _create_blocking_request()
        receiver = msgutil.MessageReceiver(request)

        self.assertEqual(None, receiver.receive_nowait())

        request.connection.put_bytes('\x04\x06Hello!')
        self.assertEqual('Hello!', receiver.receive())

    def test_onmessage(self):
        onmessage_queue = Queue.Queue()
        def onmessage_handler(message):
            onmessage_queue.put(message)

        request = _create_blocking_request()
        receiver = msgutil.MessageReceiver(request, onmessage_handler)

        request.connection.put_bytes('\x04\x06Hello!')
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
        self.assertEqual('\x04\x05World', request.connection.written_data())

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
        self.assertEqual('\x04\x05Hello', send_queue.get())
        self.assertEqual('\x04\x05World', send_queue.get())


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
