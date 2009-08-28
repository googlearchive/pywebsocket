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


"""Web Socket Echo client.

This is an example Web Socket client that talks with echo_wsh.py.
This may be useful for checking mod_pywebsocket installation.

Note:
This code is far from robust, e.g., we cut corners in handshake.
"""


import codecs
from optparse import OptionParser
import socket
import sys


_DEFAULT_PORT=81
_IMPLICIT_PORT=80


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
        try:
            self._socket.connect((self._options.server_host,
                                  self._options.server_port))
            self._handshake()
            for line in self._options.message.split(','):
                frame = '\x00' + line.encode('utf-8') + '\xff'
                self._socket.send(frame)
                if self._options.verbose:
                    print 'Send: %s' % line
                received = self._socket.recv(len(frame))
                if received != frame:
                    raise Exception('Incorrect echo: %r' % received)
                if self._options.verbose:
                    print 'Recv: %s' % received[1:-1].decode('utf-8')
        finally:
            self._socket.close()

    def _handshake(self):
        self._socket.send(
                'GET %s HTTP/1.1\r\n' % self._options.resource)
        self._socket.send('Upgrade: WebSocket\r\n')
        self._socket.send('Connection: Upgrade\r\n')
        self._socket.send(self._format_host_header())
        self._socket.send(
                'Origin: %s\r\n' % self._options.origin)
        self._socket.send('\r\n')

        for expected_char in (
                'HTTP/1.1 101 Web Socket Protocol Handshake\r\n'
                'Upgrade: WebSocket\r\n'
                'Connection: Upgrade\r\n'):
            received = self._socket.recv(1)[0]
            if expected_char != received:
                raise Exception('Handshake failure')
        # We cut corners and skip other headers.
        self._skip_headers()

    def _skip_headers(self):
        terminator = '\r\n\r\n'
        pos = 0
        while pos < len(terminator):
            received = self._socket.recv(1)[0]
            if received == terminator[pos]:
                pos += 1
            else:
                pos = 0

    def _format_host_header(self):
        host = 'Host: ' + self._options.server_host
        if self._options.server_port != _IMPLICIT_PORT:
            host += ':' + str(self._options.server_port)
        host += '\r\n'
        return host


def main():
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout)

    parser = OptionParser()
    parser.add_option('-s', '--server_host', dest='server_host', type='string',
                      default='localhost', help='server host')
    parser.add_option('-p', '--server_port', dest='server_port', type='int',
                      default=_DEFAULT_PORT, help='server port')
    parser.add_option('-o', '--origin', dest='origin', type='string',
                      default='http://localhost/', help='origin')
    parser.add_option('-r', '--resource', dest='resource', type='string',
                      default='/echo', help='resource path')
    parser.add_option('-m', '--message', dest='message', type='string',
                      default=u'Hello,\u65e5\u672c',  # "Japan" in Japanese
                      help='comma-separated messages to send')
    parser.add_option('-q', '--quiet', dest='verbose', action='store_false',
                      default=True, help='suppress messages')
    (options, _) = parser.parse_args()

    EchoClient(options).run()


if __name__ == '__main__':
    main()


# vi:sts=4 sw=4 et
