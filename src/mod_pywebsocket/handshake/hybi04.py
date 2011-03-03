# Copyright 2011, Google Inc.
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


"""WebSocket HyBi 04 opening handshake processor.
"""


import base64
import logging
import os
import re

from mod_pywebsocket import common
from mod_pywebsocket import stream
from mod_pywebsocket import util
from mod_pywebsocket.handshake._base import HandshakeError
from mod_pywebsocket.handshake._base import check_header_lines
from mod_pywebsocket.handshake._base import get_mandatory_header


_MANDATORY_HEADERS = [
    # key, expected value or None
    ['Upgrade', 'websocket'],
    ['Connection', 'Upgrade'],
]

_BASE64_REGEX = re.compile('^[+/0-9A-Za-z]*=*$')


class Handshaker(object):
    """This class performs WebSocket handshake."""

    def __init__(self, request, dispatcher):
        """Construct an instance.

        Args:
            request: mod_python request.
            dispatcher: Dispatcher (dispatch.Dispatcher).

        Handshaker will add attributes such as ws_resource during handshake.
        """

        self._logger = util.get_class_logger(self)

        self._request = request
        self._dispatcher = dispatcher

    def do_handshake(self):
        check_header_lines(self._request, _MANDATORY_HEADERS)
        self._request.ws_resource = self._request.uri

        unused_host = get_mandatory_header(self._request, 'Host')

        self._get_origin()
        self._check_version()
        self._set_protocol()
        self._set_extensions()

        key = self._get_key()
        original_nonce = self._generate_nonce()
        nonce = base64.b64encode(original_nonce)
        self._logger.debug('server nonce : %s (%s)' %
                           (nonce, util.hexify(original_nonce)))
        original_accept = util.sha1_hash(
            key + common.WEBSOCKET_ACCEPT_UUID).digest()
        accept = base64.b64encode(original_accept)
        self._logger.debug('server accept : %s (%s)' %
                           (accept, util.hexify(original_accept)))

        self._set_masking_key(key, nonce)

        self._send_handshake(nonce, accept)

        self._logger.debug('IETF HyBi 04 protocol')
        self._request.ws_version = common.VERSION_HYBI04
        self._request.ws_stream = stream.Stream(self._request)

    def _get_origin(self):
        origin = get_mandatory_header(self._request, 'Sec-WebSocket-Origin')
        self._request.ws_origin = origin

    def _check_version(self):
        unused_value = get_mandatory_header(
            self._request, 'Sec-WebSocket-Version', '4')

    def _set_protocol(self):
        protocol_header = self._request.headers_in.get(
            'Sec-WebSocket-Protocol')

        if not protocol_header:
            self._request.ws_protocol = None
            return

        requested_protocols = protocol_header.split(',')
        # TODO(tyoshino): Follow the ABNF in the spec.
        requested_protocols = [s.strip() for s in requested_protocols]

        self._request.ws_protocol = ''

        # TODO(tyoshino): Add subprotocol processing code. For now, we reject
        # any subprotocol by leaving self._request.ws_protocol empty. We need
        # some framework to register available subprotocols.

        self._logger.debug('protocols requested : %r', requested_protocols)
        self._logger.debug(
            'protocol accepted  : %r', self._request.ws_protocol)

    def _set_extensions(self):
        self._request.ws_deflate = False

        extensions_header = self._request.headers_in.get(
            'Sec-WebSocket-Extensions')
        if not extensions_header:
            self._request.ws_extensions = None
            return

        self._request.ws_extensions = []

        requested_extensions = extensions_header.split(',')
        # TODO(tyoshino): Follow the ABNF in the spec.
        requested_extensions = [s.strip() for s in requested_extensions]

        for extension in requested_extensions:
            # We now support only deflate-stream extension. Any other
            # extension requests are just ignored for now.
            if extension == 'deflate-stream':
                self._request.ws_extensions.append(extension)
                self._request.ws_deflate = True

        self._logger.debug('extensions requested : %r', requested_extensions)
        self._logger.debug(
            'extensions accepted  : %r', self._request.ws_extensions)

    def _validate_key(self, key):
        # Validate
        key_is_valid = False
        try:
            # Validate key by quick regex match before parsing by base64
            # module. Because base64 module skips invalid characters, we have
            # to do this in advance to make this server strictly reject illegal
            # keys.
            if _BASE64_REGEX.match(key):
                decoded_key = base64.b64decode(key)
                if len(decoded_key) == 16:
                    key_is_valid = True
        except TypeError, e:
            pass

        if not key_is_valid:
            raise HandshakeError(
                'Illegal value for header Sec-WebSocket-Key: ' + key)

        return decoded_key

    def _get_key(self):
        key = get_mandatory_header(self._request, 'Sec-WebSocket-Key')

        decoded_key = self._validate_key(key)

        self._logger.debug('client nonce : %s (%s)' %
                           (key, util.hexify(decoded_key)))

        return key

    def _generate_nonce(self):
        # TODO(tyoshino): os.urandom does open/read/close for every call. If
        # performance matters, change this to some library call that generates
        # cryptographically secure pseudo random number sequence.
        return os.urandom(16)

    def _set_masking_key(self, key, nonce):
        self._request.ws_masking_key = util.sha1_hash(
            key + nonce + common.WEBSOCKET_MASKING_UUID).digest()
        self._logger.debug('masking-key  : %s' %
                           util.hexify(self._request.ws_masking_key))

    def _send_handshake(self, nonce, accept):
        self._request.connection.write(
            'HTTP/1.1 101 Switching Protocols\r\n')
        self._request.connection.write('Upgrade: websocket\r\n')
        self._request.connection.write('Connection: Upgrade\r\n')
        self._request.connection.write('Sec-WebSocket-Accept: %s\r\n' % accept)
        self._request.connection.write('Sec-WebSocket-Nonce: %s\r\n' % nonce)
        # TODO(tyoshino): Encode value of protocol and extensions if any
        # special character that we have to encode by some manner.
        if self._request.ws_protocol is not None:
            self._request.connection.write('Sec-WebSocket-Protocol: %s\r\n' %
                                           self._request.ws_protocol)
        if self._request.ws_extensions is not None:
            self._request.connection.write(
                'Sec-WebSocket-Extensions: %s\r\n' %
                ', '.join(self._request.ws_extensions))
        self._request.connection.write('\r\n')


# vi:sts=4 sw=4 et
