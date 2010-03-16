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


"""Web Socket Echo client.

This is an example Web Socket client that talks with echo_wsh.py.
This may be useful for checking mod_pywebsocket installation.

Note:
This code is far from robust, e.g., we cut corners in handshake.

Example Usage:

# server setup
 % cd $pywebsocket
 % PYTHONPATH=$cwd/src python ./mod_pywebsocket/standalone.py -p 8880 \
    -d $cwd/src/example

# run client
 % python ./example/echo_client.py -p 8880 -s localhost -o http://localhost \
     -r /echo -m test

or
# server setup to test old protocol
 run with --allow-draft75

# run client
 run with --draft75
"""


import codecs
import logging
from md5 import md5
from optparse import OptionParser
import random
import re
import socket
import struct
import sys


_TIMEOUT_SEC = 10
_DEFAULT_PORT = 80
_DEFAULT_SECURE_PORT = 443
_UNDEFINED_PORT = -1

_GOODBYE_MESSAGE = 'Goodbye'


def _method_line(resource):
    return 'GET %s HTTP/1.1\r\n' % resource


def _origin_header(origin):
    return 'Origin: %s\r\n' % origin

def _hexify(s):
    return re.sub(".", lambda x: "%02x " % ord(x.group(0)), s)


class _TLSSocket(object):
    """Wrapper for a TLS connection."""

    def __init__(self, raw_socket):
        self._ssl = socket.ssl(raw_socket)

    def send(self, bytes):
        return self._ssl.write(bytes)

    def recv(self, size=-1):
        return self._ssl.read(size)

    def close(self):
        # Nothing to do.
        pass


class WebSocketHandshake(object):
    """Web Socket handshake (draft 76 or later)."""

    _UPGRADE_HEADER = 'Upgrade: WebSocket\r\n'
    _CONNECTION_HEADER = 'Connection: Upgrade\r\n'

    def __init__(self, socket, options):
        self._socket = socket
        self._options = options

    def handshake(self):
        """Handshake Web Socket.

        Raises:
          Exception: handshake failed.
        """
        self._socket.send(_method_line(self._options.resource))
        fields = []
        fields.append(WebSocketHandshake._UPGRADE_HEADER)
        fields.append(WebSocketHandshake._CONNECTION_HEADER)
        fields.append(self._format_host_header())
        fields.append(_origin_header(self._options.origin))
        self._number1, key1 = self._generate_sec_websocket_key()
        fields.append('Sec-WebSocket-Key1: ' + key1 + '\r\n')
        self._number2, key2 = self._generate_sec_websocket_key()
        fields.append('Sec-WebSocket-Key2: ' + key2 + '\r\n')

        fields.sort(cmp=lambda _i, _j: random.randint(-1, 1))
        for field in fields:
            self._socket.send(field)
        self._socket.send('\r\n')
        self._key3 = self._generate_key3()
        self._socket.send(self._key3)
        logging.info("%s" % _hexify(self._key3))

        status_line = ""
        while True:
            ch = self._socket.recv(1)
            status_line += ch
            if ch == '\n':
                break
        if len(status_line) < 7 or not status_line.endswith('\r\n'):
            raise Exception('wrong status line: %s' % status_line)
        m = re.match("[^ ]* ([^ ]*) .*", status_line)
        if m is None:
            raise Exception('no code found in: %s' % status_line)
        code = m.group(1)
        if not re.match("[0-9][0-9][0-9]", code):
            raise Exception('wrong code %s in: %s' % (code, status_line))
        if code != "101":
            raise Exception('unexpected code in: %s' % status_line)
        fields = self._read_fields()

    def _generate_sec_websocket_key(self):
        spaces = random.randint(1, 12)
        maxnum = 4294967295 / spaces
        number = random.randint(0, maxnum)
        product = number * spaces
        key = str(product)
        for _ in range(spaces):
            pos = random.randint(1, len(key) - 1)
            key = key[0:pos] + ' ' + key[pos:]
        available_chars = range(0x21, 0x2f) + range(0x3a, 0x7e)
        for _ in range(12):
            ch = available_chars[random.randint(0, len(available_chars) - 1)]
            pos = random.randint(0, len(key))
            key = key[0:pos] + chr(ch) + key[pos:]
        return number, key

    def _generate_key3(self):
        key3 = ""
        for _ in range(8):
            key3 += chr(random.randint(0, 255))
        return key3

    def _read_fields(self):
        fields = {}
        while True:
            name = self._read_name()
            if name is None:
                break
            value = self._read_value()
            ch = self._socket.recv(1)[0]
            if ch != '\n':
                raise Exception('expected LF after line: %s: %s' % (
                    name, value))
            fields.setdefault(name, []).append(value)

        # Fields processing
        ch = self._socket.recv(1)[0]
        if ch != '\n':
            raise Exception('expected LF after line: %s: %s' % (name, value))
        if len(fields['upgrade']) != 1:
            raise Exception('not one ugprade: %s' % fields['upgrade'])
        if len(fields['connection']) != 1:
            raise Exception('not one connection: %s' % fields['connection'])
        if len(fields['sec-websocket-origin']) != 1:
            raise Exception('not one sec-websocket-origin: %s' %
                            fields['sec-sebsocket-origin'])
        if len(fields['sec-websocket-location']) != 1:
            raise Exception('not one sec-websocket-location: %s' %
                            fields['sec-sebsocket-location'])
        # TODO(ukai): protocol
        if fields['upgrade'][0] != 'WebSocket':
            raise Exception('unexpected upgrade: %s' % fields['upgrade'][0])
        if fields['connection'][0].lower() != 'upgrade':
            raise Exception('unexpected connection: %s' %
                            fields['connection'][0])
        # TODO(ukai): check origin, location, cookie, ..

        challenge = struct.pack("!I", self._number1)
        challenge += struct.pack("!I", self._number2)
        challenge += self._key3

        logging.info("num %d, %d, %s" % (
            self._number1, self._number2,
            _hexify(self._key3)))
        logging.info("challenge: %s" % _hexify(challenge))

        expected = md5(challenge).digest()
        logging.info("expected : %s" % _hexify(expected))

        reply = self._socket.recv(16)
        logging.info("reply    : %s" % _hexify(reply))

        if expected != reply:
            raise Exception('challenge/response failed: %s != %s' % (
                expected, reply))
        # connection is established.

    def _read_name(self):
        name = ""
        while True:
            ch = self._socket.recv(1)[0]
            if ch == '\r':
                return None
            elif ch == '\n':
                raise Exception('unexpected LF in name reading')
            elif ch == ':':
                return name
            elif ch >= 'A' and ch <= 'Z':
                ch = chr(ord(ch) + 0x20)
                name += ch
            else:
                name += ch

    def _read_value(self):
        value = ""
        while True:
            ch = self._socket.recv(1)[0]
            if ch == ' ':
                continue
            value = ch
            break
        while True:
            ch = self._socket.recv(1)[0]
            if ch == '\r':
                return value
            elif ch == '\n':
                raise Exception('unexpected LF in value reading')
            else:
                value += ch

    def _skip_headers(self):
        terminator = '\r\n\r\n'
        pos = 0
        while pos < len(terminator):
            received = self._socket.recv(1)[0]
            if received == terminator[pos]:
                pos += 1
            elif received == terminator[0]:
                pos = 1
            else:
                pos = 0

    def _format_host_header(self):
        host = 'Host: ' + self._options.server_host.lower()
        if ((not self._options.use_tls and
             self._options.server_port != _DEFAULT_PORT) or
            (self._options.use_tls and
             self._options.server_port != _DEFAULT_SECURE_PORT)):
            host += ':' + str(self._options.server_port)
        host += '\r\n'
        return host


class WebSocketDraft75Handshake(WebSocketHandshake):
    """Web Socket draft 75 handshake."""

    _EXPECTED_RESPONSE = (
        'HTTP/1.1 101 Web Socket Protocol Handshake\r\n' +
        WebSocketHandshake._UPGRADE_HEADER +
        WebSocketHandshake._CONNECTION_HEADER)

    def __init__(self, socket, options):
        WebSocketHandshake.__init__(self, socket, options)

    def handshake(self):
        self._socket.send(_method_line(self._options.resource))
        self._socket.send(WebSocketHandshake._UPGRADE_HEADER)
        self._socket.send(WebSocketHandshake._CONNECTION_HEADER)
        self._socket.send(self._format_host_header())
        self._socket.send(_origin_header(self._options.origin))
        self._socket.send('\r\n')

        for expected_char in WebSocketDraft75Handshake._EXPECTED_RESPONSE:
            received = self._socket.recv(1)[0]
            if expected_char != received:
                raise Exception('Handshake failure')
        # We cut corners and skip other headers.
        self._skip_headers()

class EchoClient(object):
    """Web Socket echo client."""

    def __init__(self, options):
        self._options = options
        self._socket = None

    def run(self):
        """Run the client.

        Shake hands and then repeat sending message and receiving its echo.
        """
        self._socket = socket.socket()
        self._socket.settimeout(self._options.socket_timeout)
        try:
            self._socket.connect((self._options.server_host,
                                  self._options.server_port))
            if self._options.use_tls:
                self._socket = _TLSSocket(self._socket)

            if self._options.draft75:
                self._handshake = WebSocketDraft75Handshake(
                    self._socket, self._options)
            else:
                self._handshake = WebSocketHandshake(
                    self._socket, self._options)
            self._handshake.handshake()

            for line in self._options.message.split(',') + [_GOODBYE_MESSAGE]:
                frame = '\x00' + line.encode('utf-8') + '\xff'
                self._socket.send(frame)
                if self._options.verbose:
                    print 'Send: %s' % line
                received = self._socket.recv(len(frame))
                if received != frame:
                    raise Exception('Incorrect echo: %r' % received)
                if self._options.verbose:
                    print 'Recv: %s' % received[1:-1].decode('utf-8',
                                                             'replace')
        finally:
            self._socket.close()

def main():
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout)

    parser = OptionParser()
    parser.add_option('-s', '--server-host', '--server_host',
                      dest='server_host', type='string',
                      default='localhost', help='server host')
    parser.add_option('-p', '--server-port', '--server_port',
                      dest='server_port', type='int',
                      default=_UNDEFINED_PORT, help='server port')
    parser.add_option('-o', '--origin', dest='origin', type='string',
                      default='http://localhost/', help='origin')
    parser.add_option('-r', '--resource', dest='resource', type='string',
                      default='/echo', help='resource path')
    parser.add_option('-m', '--message', dest='message', type='string',
                      help=('comma-separated messages to send excluding "%s" '
                            'that is always sent at the end' %
                            _GOODBYE_MESSAGE))
    parser.add_option('-q', '--quiet', dest='verbose', action='store_false',
                      default=True, help='suppress messages')
    parser.add_option('-t', '--tls', dest='use_tls', action='store_true',
                      default=False, help='use TLS (wss://)')
    parser.add_option('-k', '--socket-timeout', '--socket_timeout',
                      dest='socket_timeout', type='int', default=_TIMEOUT_SEC,
                      help='Timeout(sec) for sockets')
    parser.add_option('--draft75', dest='draft75',
                      action='store_true', default=False,
                      help='use draft-75 handshake protocol')

    (options, unused_args) = parser.parse_args()

    # Default port number depends on whether TLS is used.
    if options.server_port == _UNDEFINED_PORT:
        if options.use_tls:
            options.server_port = _DEFAULT_SECURE_PORT
        else:
            options.server_port = _DEFAULT_PORT

    # optparse doesn't seem to handle non-ascii default values.
    # Set default message here.
    if not options.message:
        options.message = u'Hello,\u65e5\u672c'   # "Japan" in Japanese

    EchoClient(options).run()


if __name__ == '__main__':
    main()


# vi:sts=4 sw=4 et
