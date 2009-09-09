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


"""Web Socket handshaking."""


import re


_DEFAULT_WEB_SOCKET_PORT = 80
_DEFAULT_WEB_SOCKET_SECURE_PORT = 443
_WEB_SOCKET_SCHEME = 'ws'
_WEB_SOCKET_SECURE_SCHEME = 'wss'

_METHOD_LINE = re.compile(r'^GET ([^ ]+) HTTP/1.1\r\n$')

_MANDATORY_HEADERS = [
    # key, expected value or None
    ['Upgrade', 'WebSocket'],
    ['Connection', 'Upgrade'],
    ['Host', None],
    ['Origin', None],
]


class HandshakeError(Exception):
    """Exception in Web Socket Handshake."""

    pass


def _validate_protocol(protocol):
    """Validate WebSocket-Protocol string."""

    if not protocol:
        raise HandshakeError('Invalid WebSocket-Protocol: empty')
    for c in protocol:
        if not 0x21 <= ord(c) <= 0x7e:
            raise HandshakeError('Illegal character in protocol: %r' % c)


class Handshaker(object):
    """This class performs Web Socket handshake."""

    def __init__(self, conn_context, dispatcher):
        """Construct an instance.

        Args:
            conn_context: Connection context (conncontext.ConnContext).
            dispatcher: Dispatcher (dispatch.Dispatcher).

        Handshaker will change the attributes of conn_context in performing
        handshake.
        """

        self._conn_context = conn_context
        self._dispatcher = dispatcher

    def shake_hands(self):
        """Perform Web Socket Handshake."""

        self._receive_handshake()
        self._set_origin()
        self._set_location()
        self._set_protocol()
        self._dispatcher.shake_hands(self._conn_context)
        self._send_handshake()

    def _receive_handshake(self):
        self._check_method_line()
        self._check_header_lines()

    def _set_origin(self):
        self._conn_context.origin = self._conn_context.headers['Origin']

    def _set_location(self):
        location_parts = []
        if self._conn_context.secure:
            location_parts.append(_WEB_SOCKET_SECURE_SCHEME)
        else:
            location_parts.append(_WEB_SOCKET_SCHEME)
        location_parts.append('://')
        host, port = self._parse_host_header()
        conn_port = self._conn_context.conn.local_addr[1]
        if port != conn_port:
            raise HandshakeError('Header/connection port mismatch: %d/%d' %
                                 (port, conn_port))
        location_parts.append(host)
        if ((not self._conn_context.secure and
             port != _DEFAULT_WEB_SOCKET_PORT) or
            (self._conn_context.secure and
             port != _DEFAULT_WEB_SOCKET_SECURE_PORT)):
            location_parts.append(':')
            location_parts.append(str(port))
        location_parts.append(self._conn_context.resource)
        self._conn_context.location = ''.join(location_parts)

    def _parse_host_header(self):
        fields = self._conn_context.headers['Host'].split(':', 1)
        if len(fields) == 1:
            port = _DEFAULT_WEB_SOCKET_PORT
            if self._conn_context.secure:
                port = _DEFAULT_WEB_SOCKET_SECURE_PORT
            return fields[0], port
        try:
            return fields[0], int(fields[1])
        except ValueError, e:
            raise HandshakeError('Invalid port number format: %r' % e)

    def _set_protocol(self):
        self._conn_context.protocol = None
        if 'WebSocket-Protocol' in self._conn_context.headers:
            protocol = self._conn_context.headers['WebSocket-Protocol']
            _validate_protocol(protocol)
            self._conn_context.protocol = protocol

    def _send_handshake(self):
        self._conn_context.conn.write(
                'HTTP/1.1 101 Web Socket Protocol Handshake\r\n')
        self._conn_context.conn.write('Upgrade: WebSocket\r\n')
        self._conn_context.conn.write('Connection: Upgrade\r\n')
        self._conn_context.conn.write('WebSocket-Origin: ')
        self._conn_context.conn.write(self._conn_context.origin)
        self._conn_context.conn.write('\r\n')
        self._conn_context.conn.write('WebSocket-Location: ')
        self._conn_context.conn.write(self._conn_context.location)
        self._conn_context.conn.write('\r\n')
        if self._conn_context.protocol:
            self._conn_context.conn.write('WebSocket-Protocol: ')
            self._conn_context.conn.write(self._conn_context.protocol)
            self._conn_context.conn.write('\r\n')
        self._conn_context.conn.write('\r\n')

    def _check_method_line(self):
        line = self._conn_context.conn.readline()
        match = _METHOD_LINE.search(line)
        if match:
            self._conn_context.resource = match.group(1)
            return
        raise HandshakeError('Invalid method line: %r' % line)

    def _check_header_lines(self):
        self._conn_context.headers = {}
        for key, expected_value in _MANDATORY_HEADERS:
            line = self._conn_context.conn.readline()
            self._add_header(key, expected_value, line)
        while True:
            line = self._conn_context.conn.readline()
            if line == '\r\n':
                return
            key_end = line.find(':')
            if key_end == -1:
                continue
            key = line[:key_end]
            self._add_header(key, None, line)

    def _add_header(self, key, expected_value, line):
        if not line.endswith('\r\n') or not line.startswith(key + ':'):
            # Header is missing or not in the correct order.
            raise HandshakeError('Header %r not defined in: %r' % (key, line))
        start = len(key) + 1
        if line[start] == ' ':
            # Skip a space if necessary.
            start += 1
        value = line[start:-2]
        if expected_value and expected_value != value:
            raise HandshakeError('Unexpected value: %r for: %r' % (value, key))
        self._conn_context.headers[key] = value


# vi:sts=4 sw=4 et
