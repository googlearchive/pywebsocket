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


class MessageTest(unittest.TestCase):
    def test_send_message(self):
        conn = mock.MockConn('')
        msgutil.send_message(conn, 'Hello')
        self.assertEqual('\x00Hello\xff', conn.written_data())

    def test_send_message_unicode(self):
        conn = mock.MockConn('')
        msgutil.send_message(conn, u'\u65e5')
        # U+65e5 is encoded as e6,97,a5 in UTF-8
        self.assertEqual('\x00\xe6\x97\xa5\xff', conn.written_data())

    def test_receive_message(self):
        conn = mock.MockConn('\x00Hello\xff\x00World!\xff')
        self.assertEqual('Hello', msgutil.receive_message(conn))
        self.assertEqual('World!', msgutil.receive_message(conn))

    def test_receive_message_unicode(self):
        conn = mock.MockConn('\x00\xe6\x9c\xac\xff')
        # U+672c is encoded as e6,9c,ac in UTF-8
        self.assertEqual(u'\u672c', msgutil.receive_message(conn))

    def test_receive_message_discard(self):
        conn = mock.MockConn('\x80\x06IGNORE\x00Hello\xff'
                                '\x01DISREGARD\xff\x00World!\xff')
        self.assertEqual('Hello', msgutil.receive_message(conn))
        self.assertEqual('World!', msgutil.receive_message(conn))

    def test_payload_length(self):
        for length, bytes in ((0, '\x00'), (0x7f, '\x7f'), (0x80, '\x81\x00'),
                              (0x1234, '\x80\xa4\x34')):
            self.assertEqual(length,
                             msgutil._payload_length(mock.MockConn(bytes)))

    def test_receive_bytes(self):
        conn = mock.MockConn('abcdefg')
        self.assertEqual('abc', msgutil._receive_bytes(conn, 3))
        self.assertEqual('defg', msgutil._receive_bytes(conn, 4))

    def test_read_until(self):
        conn = mock.MockConn('abcXdefgX')
        self.assertEqual('abc', msgutil._read_until(conn, 'X'))
        self.assertEqual('defg', msgutil._read_until(conn, 'X'))


class MessageReceiverTest(unittest.TestCase):
    def test_queue(self):
        conn = mock.MockBlockingConn()
        receiver = msgutil.MessageReceiver(conn)

        self.assertEqual(None, receiver.receive_nowait())

        conn.put_bytes('\x00Hello!\xff')
        self.assertEqual('Hello!', receiver.receive())

    def test_onmessage(self):
        onmessage_queue = Queue.Queue()
        def onmessage_handler(message):
            onmessage_queue.put(message)

        conn = mock.MockBlockingConn()
        receiver = msgutil.MessageReceiver(conn, onmessage_handler)

        conn.put_bytes('\x00Hello!\xff')
        self.assertEqual('Hello!', onmessage_queue.get())


class MessageSenderTest(unittest.TestCase):
    def test_send(self):
        conn = mock.MockBlockingConn()
        sender = msgutil.MessageSender(conn)

        sender.send('World')
        self.assertEqual('\x00World\xff', conn.written_data())

    def test_send_nowait(self):
        # Use a queue to check the bytes written by MessageSender.
        # conn.written_data() cannot be used here because MessageSender runs in
        # a separate thread.
        send_queue = Queue.Queue()
        def write(bytes):
            send_queue.put(bytes)
        conn = mock.MockBlockingConn()
        conn.write = write

        sender = msgutil.MessageSender(conn)

        sender.send_nowait('Hello')
        sender.send_nowait('World')
        self.assertEqual('\x00Hello\xff', send_queue.get())
        self.assertEqual('\x00World\xff', send_queue.get())


if __name__ == '__main__':
    unittest.main()


# vi:sts=4 sw=4 et
