#!/usr/bin/env python
#
# Copyright 2009 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Tests for msgutil module."""


import Queue
import unittest

import config  # This must be imported before mod_pywebsocket.
from mod_pywebsocket import msgutil

import mock


def _create_request(read_data):
    return mock.MockRequest(connection=mock.MockConn(read_data))

def _create_blocking_request():
    return mock.MockRequest(connection=mock.MockBlockingConn())

class MessageTest(unittest.TestCase):
    def test_send_message(self):
        request = _create_request('')
        msgutil.send_message(request, 'Hello')
        self.assertEqual('\x00Hello\xff', request.connection.written_data())

    def test_send_message_unicode(self):
        request = _create_request('')
        msgutil.send_message(request, u'\u65e5')
        # U+65e5 is encoded as e6,97,a5 in UTF-8
        self.assertEqual('\x00\xe6\x97\xa5\xff',
                         request.connection.written_data())

    def test_receive_message(self):
        request = _create_request('\x00Hello\xff\x00World!\xff')
        self.assertEqual('Hello', msgutil.receive_message(request))
        self.assertEqual('World!', msgutil.receive_message(request))

    def test_receive_message_unicode(self):
        request = _create_request('\x00\xe6\x9c\xac\xff')
        # U+672c is encoded as e6,9c,ac in UTF-8
        self.assertEqual(u'\u672c', msgutil.receive_message(request))

    def test_receive_message_discard(self):
        request = _create_request('\x80\x06IGNORE\x00Hello\xff'
                                '\x01DISREGARD\xff\x00World!\xff')
        self.assertEqual('Hello', msgutil.receive_message(request))
        self.assertEqual('World!', msgutil.receive_message(request))

    def test_payload_length(self):
        for length, bytes in ((0, '\x00'), (0x7f, '\x7f'), (0x80, '\x81\x00'),
                              (0x1234, '\x80\xa4\x34')):
            self.assertEqual(length,
                             msgutil._payload_length(_create_request(bytes)))

    def test_receive_bytes(self):
        request = _create_request('abcdefg')
        self.assertEqual('abc', msgutil._receive_bytes(request, 3))
        self.assertEqual('defg', msgutil._receive_bytes(request, 4))

    def test_read_until(self):
        request = _create_request('abcXdefgX')
        self.assertEqual('abc', msgutil._read_until(request, 'X'))
        self.assertEqual('defg', msgutil._read_until(request, 'X'))


class MessageReceiverTest(unittest.TestCase):
    def test_queue(self):
        request = _create_blocking_request()
        receiver = msgutil.MessageReceiver(request)

        self.assertEqual(None, receiver.receive_nowait())

        request.connection.put_bytes('\x00Hello!\xff')
        self.assertEqual('Hello!', receiver.receive())

    def test_onmessage(self):
        onmessage_queue = Queue.Queue()
        def onmessage_handler(message):
            onmessage_queue.put(message)

        request = _create_blocking_request()
        receiver = msgutil.MessageReceiver(request, onmessage_handler)

        request.connection.put_bytes('\x00Hello!\xff')
        self.assertEqual('Hello!', onmessage_queue.get())


class MessageSenderTest(unittest.TestCase):
    def test_send(self):
        request = _create_blocking_request()
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
        request = _create_blocking_request()
        request.connection.write = write

        sender = msgutil.MessageSender(request)

        sender.send_nowait('Hello')
        sender.send_nowait('World')
        self.assertEqual('\x00Hello\xff', send_queue.get())
        self.assertEqual('\x00World\xff', send_queue.get())


if __name__ == '__main__':
    unittest.main()


# vi:sts=4 sw=4 et
