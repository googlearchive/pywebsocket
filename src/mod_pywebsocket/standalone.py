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


"""Standalone Web Socket server.

Use this server to run mod_pywebsocket without Apache HTTP Server.

Usage:
    python standalone.py [-p <ws_port>] [-w <websock_handlers>]
                         [-d <document_root>]

<ws_port> is the port number to use for ws:// connection.

<document_root> is the path to the root directory of HTML files.

<websock_handlers> is the path to the root directory of Web Socket handlers.
See __init__.py for details of <websock_handlers> and how to write Web Socket
handlers. If this path is relative, <document_root> is used as the base.

Note:
This server is derived from SocketServer.ThreadingMixIn. Hence a thread is
used for each request.
"""

import BaseHTTPServer
import SimpleHTTPServer
import SocketServer
import logging
import optparse
import os
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
                      help='Web Socket handlers root directory.')
    parser.add_option('-d', '--document_root', dest='document_root',
                      default='.',
                      help='Document root directory.')
    # TODO(yuzo): Add wss-related options.
    WebSocketRequestHandler.options = parser.parse_args()[0]

    os.chdir(WebSocketRequestHandler.options.document_root)

    WebSocketServer(('', WebSocketRequestHandler.options.port),
                    WebSocketRequestHandler).serve_forever()


if __name__ == '__main__':
    _main()


# vi:sts=4 sw=4 et
