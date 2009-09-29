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


"""Standalone Web Socket server.

Use this server to run mod_pywebsocket without Apache HTTP Server.
"""

import BaseHTTPServer
import SimpleHTTPServer
import SocketServer
import logging
import optparse
import urlparse

import dispatch
import handshake


class _StandaloneConnection(object):
    """Mimic mod_python mp_conn."""

    def __init__(self, request_handler):
        """Construct an instance.

        Args:
            request_handler: A WebSocketRequestHandler instance.
        """
        self._request_handler = request_handler

    def get_local_addr(self):
        """Getter to mimic mp_conn.local_addr."""
        return (self._request_handler.server.server_name,
                self._request_handler.server.server_port)
    local_addr = property(get_local_addr)

    def write(self, data):
        """Mimic mp_conn.write()."""
        return self._request_handler.wfile.write(data)

    def read(self, length):
        """Mimic mp_conn.read()."""
        return self._request_handler.rfile.read(length)


class _StandaloneRequest(object):
    """Mimic mod_python request."""

    def __init__(self, request_handler):
        """Construct an instance.

        Args:
            request_handler: A WebSocketRequestHandler instance.
        """
        self._request_handler = request_handler
        self.connection = _StandaloneConnection(request_handler)

    def get_uri(self):
        """Getter to mimic request.uri."""
        return self._request_handler.path
    uri = property(get_uri)

    def get_headers_in(self):
        """Getter to mimic request.headers_in."""
        return self._request_handler.headers
    headers_in = property(get_headers_in)

    def is_https(self):
        """Mimic request.is_https()."""
        # TODO(yuzo): Implement this.
        return False


class WebSocketServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    """HTTPServer specialized for Web Socket."""

    daemon_threads = True
    pass


class WebSocketRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler specialized for Web Socket."""

    def __init__(self, *args, **keywords):
        self._request = _StandaloneRequest(self)
        self._dispatcher = dispatch.Dispatcher(
                WebSocketRequestHandler.options.websock_handlers)
        self._print_warnings_if_any()
        self._handshaker = handshake.Handshaker(self._request,
                                                self._dispatcher)
        SimpleHTTPServer.SimpleHTTPRequestHandler.__init__(
                self, *args, **keywords)

    def _print_warnings_if_any(self):
        warnings = self._dispatcher.source_warnings()
        if warnings:
            for warning in warnings:
                logging.warning('mod_pywebsocket: %s' % warning)

    def parse_request(self):
        """Override BaseHTTPServer.BaseHTTPRequestHandler.parse_request.

        Return True to continue processing for HTTP(S), False otherwise.
        """
        result = SimpleHTTPServer.SimpleHTTPRequestHandler.parse_request(self)
        if result:
            try:
                self._handshaker.shake_hands()
                self._dispatcher.transfer_data(self._request)
                return False
            except handshake.HandshakeError, e:
                # Handshake for ws(s) failed. Assume http(s).
                logging.info('mod_pywebsocket: %s' % e)
                return True
            except dispatch.DispatchError, e:
                logging.warning('mod_pywebsocket: %s' % e)
                return False
        return result


def _main():
    logging.basicConfig()

    parser = optparse.OptionParser()
    parser.add_option('-p', '--port', dest='port', type='int',
                      default=handshake._DEFAULT_WEB_SOCKET_PORT,
                      help='port to listen to')
    parser.add_option('-w', '--websock_handlers', dest='websock_handlers',
                      default='.',
                      help='Web Socket handlers base directory.')
    # TODO(yuzo): Add wss-related options.
    WebSocketRequestHandler.options = parser.parse_args()[0]

    WebSocketServer(('', WebSocketRequestHandler.options.port),
                    WebSocketRequestHandler).serve_forever()


if __name__ == '__main__':
    _main()


# vi:sts=4 sw=4 et
