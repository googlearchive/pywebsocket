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


"""Web Socket handshaking.

Note: request.connection.write/read are used in this module, even though
mod_python document says that they should be used only in connection handlers.
Unfortunately, we have no other options. For example, request.write/read are
not suitable because they don't allow direct raw bytes writing/reading.
"""


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

    def __init__(self, request, dispatcher):
        """Construct an instance.

        Args:
            request: mod_python request.
            dispatcher: Dispatcher (dispatch.Dispatcher).

        Handshaker will add attributes such as ws_resource in performing
        handshake.
        """

        self._request = request
        self._dispatcher = dispatcher

    def shake_hands(self):
        """Perform Web Socket Handshake."""

        self._check_header_lines()
        self._set_resource()
        self._set_origin()
        self._set_location()
        self._set_protocol()
        self._dispatcher.shake_hands(self._request)
        self._send_handshake()

    def _set_resource(self):
        self._request.ws_resource = self._request.uri

    def _set_origin(self):
        self._request.ws_origin = self._request.headers_in['Origin']

    def _set_location(self):
        location_parts = []
        if self._request.is_https():
            location_parts.append(_WEB_SOCKET_SECURE_SCHEME)
        else:
            location_parts.append(_WEB_SOCKET_SCHEME)
        location_parts.append('://')
        host, port = self._parse_host_header()
        conn_port = self._request.connection.local_addr[1]
        if port != conn_port:
            raise HandshakeError('Header/connection port mismatch: %d/%d' %
                                 (port, conn_port))
        location_parts.append(host)
        if ((not self._request.is_https() and
             port != _DEFAULT_WEB_SOCKET_PORT) or
            (self._request.is_https() and
             port != _DEFAULT_WEB_SOCKET_SECURE_PORT)):
            location_parts.append(':')
            location_parts.append(str(port))
        location_parts.append(self._request.uri)
        self._request.ws_location = ''.join(location_parts)

    def _parse_host_header(self):
        fields = self._request.headers_in['Host'].split(':', 1)
        if len(fields) == 1:
            port = _DEFAULT_WEB_SOCKET_PORT
            if self._request.is_https():
                port = _DEFAULT_WEB_SOCKET_SECURE_PORT
            return fields[0], port
        try:
            return fields[0], int(fields[1])
        except ValueError, e:
            raise HandshakeError('Invalid port number format: %r' % e)

    def _set_protocol(self):
        protocol = self._request.headers_in.get('WebSocket-Protocol')
        if protocol is not None:
            _validate_protocol(protocol)
        self._request.ws_protocol = protocol

    def _send_handshake(self):
        self._request.connection.write(
                'HTTP/1.1 101 Web Socket Protocol Handshake\r\n')
        self._request.connection.write('Upgrade: WebSocket\r\n')
        self._request.connection.write('Connection: Upgrade\r\n')
        self._request.connection.write('WebSocket-Origin: ')
        self._request.connection.write(self._request.ws_origin)
        self._request.connection.write('\r\n')
        self._request.connection.write('WebSocket-Location: ')
        self._request.connection.write(self._request.ws_location)
        self._request.connection.write('\r\n')
        if self._request.ws_protocol:
            self._request.connection.write('WebSocket-Protocol: ')
            self._request.connection.write(self._request.ws_protocol)
            self._request.connection.write('\r\n')
        self._request.connection.write('\r\n')

    def _check_header_lines(self):
        for key, expected_value in _MANDATORY_HEADERS:
            actual_value = self._request.headers_in.get(key)
            if not actual_value:
                raise HandshakeError('Header %s not defined' % key)
            if expected_value:
                if actual_value != expected_value:
                    raise HandshakeError('Illegal value for header %s: %s' %
                                         (key, actual_value))


# vi:sts=4 sw=4 et
