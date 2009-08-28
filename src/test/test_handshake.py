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


"""Tests for handshake module."""


import unittest

import config  # This must be imported before mod_pywebsocket.
from mod_pywebsocket import conncontext
from mod_pywebsocket import handshake

import mock


_GOOD_REQUEST = (
        'GET /demo HTTP/1.1\r\n'
        'Upgrade: WebSocket\r\n'
        'Connection: Upgrade\r\n'
        'Host: example.com:81\r\n'
        'Origin: http://example.com\r\n'
        'WebSocket-Protocol: sample\r\n'
        '\r\n')

_GOOD_RESPONSE_DEFAULT_PORT = (
        'HTTP/1.1 101 Web Socket Protocol Handshake\r\n'
        'Upgrade: WebSocket\r\n'
        'Connection: Upgrade\r\n'
        'WebSocket-Origin: http://example.com\r\n'
        'WebSocket-Location: ws://example.com/demo\r\n'
        'WebSocket-Protocol: sample\r\n'
        '\r\n')

_GOOD_REQUEST_PORT_80 = (
        'GET /demo HTTP/1.1\r\n'
        'Upgrade: WebSocket\r\n'
        'Connection: Upgrade\r\n'
        'Host: example.com\r\n'
        'Origin: http://example.com\r\n'
        'WebSocket-Protocol: sample\r\n'
        '\r\n')

_GOOD_RESPONSE_PORT_80 = (
        'HTTP/1.1 101 Web Socket Protocol Handshake\r\n'
        'Upgrade: WebSocket\r\n'
        'Connection: Upgrade\r\n'
        'WebSocket-Origin: http://example.com\r\n'
        'WebSocket-Location: ws://example.com:80/demo\r\n'
        'WebSocket-Protocol: sample\r\n'
        '\r\n')

_GOOD_REQUEST_NONDEFAULT_PORT = (
        'GET /demo HTTP/1.1\r\n'
        'Upgrade: WebSocket\r\n'
        'Connection: Upgrade\r\n'
        'Host: example.com:8081\r\n'
        'Origin: http://example.com\r\n'
        'WebSocket-Protocol: sample\r\n'
        '\r\n')

_GOOD_RESPONSE_NONDEFAULT_PORT = (
        'HTTP/1.1 101 Web Socket Protocol Handshake\r\n'
        'Upgrade: WebSocket\r\n'
        'Connection: Upgrade\r\n'
        'WebSocket-Origin: http://example.com\r\n'
        'WebSocket-Location: ws://example.com:8081/demo\r\n'
        'WebSocket-Protocol: sample\r\n'
        '\r\n')

_GOOD_REQUEST_NO_PROTOCOL = (
        'GET /demo HTTP/1.1\r\n'
        'Upgrade: WebSocket\r\n'
        'Connection: Upgrade\r\n'
        'Host: example.com:81\r\n'
        'Origin: http://example.com\r\n'
        '\r\n')

_GOOD_RESPONSE_NO_PROTOCOL = (
        'HTTP/1.1 101 Web Socket Protocol Handshake\r\n'
        'Upgrade: WebSocket\r\n'
        'Connection: Upgrade\r\n'
        'WebSocket-Origin: http://example.com\r\n'
        'WebSocket-Location: ws://example.com/demo\r\n'
        '\r\n')

_GOOD_REQUEST_WITH_OPTIONAL_HEADERS = (
        'GET /demo HTTP/1.1\r\n'
        'Upgrade: WebSocket\r\n'
        'Connection: Upgrade\r\n'
        'Host: example.com:81\r\n'
        'Origin: http://example.com\r\n'
        'WebSocket-Protocol: sample\r\n'
        'NoSpaces:ShouldBeOk\r\n'
        'OneSpace: ShouldBeSkipped\r\n'
        'TwoSpaces:  OneShouldRemain\r\n'
        'EmptyValue:\r\n'
        '\r\n')

_BAD_REQUESTS = [
        (  # Missing Upgrade
         "GET /demo HTTP/1.1\r\n"
         "Connection: Upgrade\r\n"
         "Host: example.com:81\r\n"
         "Origin: http://example.com\r\n"
         "WebSocket-Protocol: sample\r\n"
         "\r\n",
         81),
        (  # Wrong Upgrade
         "GET /demo HTTP/1.1\r\n"
         "Upgrade: not_websocket\r\n"
         "Connection: Upgrade\r\n"
         "Host: example.com:81\r\n"
         "Origin: http://example.com\r\n"
         "WebSocket-Protocol: sample\r\n"
         "\r\n",
         81),
        (  # Empty WebSocket-Protocol
         "GET /demo HTTP/1.1\r\n"
         "Upgrade: WebSocket\r\n"
         "Connection: Upgrade\r\n"
         "Host: example.com:81\r\n"
         "Origin: http://example.com\r\n"
         "WebSocket-Protocol: \r\n"
         "\r\n",
         81),
        (  # Wrong port number format
         "GET /demo HTTP/1.1\r\n"
         "Upgrade: WebSocket\r\n"
         "Connection: Upgrade\r\n"
         "Host: example.com:0x51\r\n"
         "Origin: http://example.com\r\n"
         "WebSocket-Protocol: sample\r\n"
         "\r\n",
         0x51),
        (  # Header/connection port mismatch
         "GET /demo HTTP/1.1\r\n"
         "Upgrade: WebSocket\r\n"
         "Connection: Upgrade\r\n"
         "Host: example.com\r\n"
         "Origin: http://example.com\r\n"
         "WebSocket-Protocol: sample\r\n"
         "\r\n",
         81),
        (  # Illegal protocol
         "GET /demo HTTP/1.1\r\n"
         "Upgrade: WebSocket\r\n"
         "Connection: Upgrade\r\n"
         "Host: example.com:81\r\n"
         "Origin: http://example.com\r\n"
         "WebSocket-Protocol: illegal protocol\r\n"
         "\r\n",
         81),
        ]


class HandshakerTest(unittest.TestCase):
    def test_validate_protocol(self):
        handshake._validate_protocol('sample')  # should succeed.
        handshake._validate_protocol('Sample')  # should succeed.
        self.assertRaises(handshake.HandshakeError,
                          handshake._validate_protocol,
                          'sample protocol')
        self.assertRaises(handshake.HandshakeError,
                          handshake._validate_protocol,
                          # "Japan" in Japanese
                          u'\u65e5\u672c')

    def test_good_request_default_port(self):
        conn = mock.MockConn(_GOOD_REQUEST)
        conn.local_addr = ('0.0.0.0', 81)
        conn_context = conncontext.ConnContext(conn)
        handshaker = handshake.Handshaker(conn_context,
                                          mock.MockDispatcher())
        handshaker.shake_hands()
        self.assertEqual(_GOOD_RESPONSE_DEFAULT_PORT, conn.written_data())
        self.assertEqual('sample', conn_context.protocol)

    def test_good_request_port_80(self):
        conn = mock.MockConn(_GOOD_REQUEST_PORT_80)
        conn.local_addr = ('0.0.0.0', 80)
        conn_context = conncontext.ConnContext(conn)
        handshaker = handshake.Handshaker(conn_context,
                                          mock.MockDispatcher())
        handshaker.shake_hands()
        self.assertEqual(_GOOD_RESPONSE_PORT_80, conn.written_data())
        self.assertEqual('sample', conn_context.protocol)

    def test_good_request_nondefault_port(self):
        conn = mock.MockConn(_GOOD_REQUEST_NONDEFAULT_PORT)
        conn.local_addr = ('0.0.0.0', 8081)
        conn_context = conncontext.ConnContext(conn)
        handshaker = handshake.Handshaker(conn_context,
                                          mock.MockDispatcher())
        handshaker.shake_hands()
        self.assertEqual(_GOOD_RESPONSE_NONDEFAULT_PORT, conn.written_data())
        self.assertEqual('sample', conn_context.protocol)

    def test_good_request_default_no_protocol(self):
        conn = mock.MockConn(_GOOD_REQUEST_NO_PROTOCOL)
        conn.local_addr = ('0.0.0.0', 81)
        conn_context = conncontext.ConnContext(conn)
        handshaker = handshake.Handshaker(conn_context,
                                          mock.MockDispatcher())
        handshaker.shake_hands()
        self.assertEqual(_GOOD_RESPONSE_NO_PROTOCOL, conn.written_data())
        self.assertEqual(None, conn_context.protocol)

    def test_port_mismatch(self):
        conn = mock.MockConn(_GOOD_REQUEST_PORT_80)
        conn.local_addr = ('0.0.0.0', 81)
        conn_context = conncontext.ConnContext(conn)
        handshaker = handshake.Handshaker(conn_context,
                                          mock.MockDispatcher())
        self.assertRaises(handshake.HandshakeError, handshaker.shake_hands)

    def test_good_request_optional_headers(self):
        conn = mock.MockConn(_GOOD_REQUEST_WITH_OPTIONAL_HEADERS)
        conn.local_addr = ('0.0.0.0', 81)
        conn_context = conncontext.ConnContext(conn)
        handshaker = handshake.Handshaker(conn_context,
                                          mock.MockDispatcher())
        handshaker.shake_hands()
        self.assertEqual('ShouldBeOk',
                         conn_context.headers['NoSpaces'])
        self.assertEqual('ShouldBeSkipped',
                         conn_context.headers['OneSpace'])
        self.assertEqual(' OneShouldRemain',
                         conn_context.headers['TwoSpaces'])
        self.assertEqual('',
                         conn_context.headers['EmptyValue'])

    def test_bad_requests(self):
        for bad_request, port in _BAD_REQUESTS:
            conn = mock.MockConn(bad_request)
            conn.local_addr = ('0.0.0.0', port)
            conn_context = conncontext.ConnContext(conn)
            handshaker = handshake.Handshaker(conn_context,
                                              mock.MockDispatcher())
            self.assertRaises(handshake.HandshakeError, handshaker.shake_hands)


if __name__ == '__main__':
    unittest.main()


# vi:sts=4 sw=4 et
