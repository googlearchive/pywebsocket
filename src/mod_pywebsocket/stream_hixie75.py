# Copyright 2010, Google Inc.
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


"""Stream of WebSocket protocol with the framing used prior to IETF HyBi 01.
"""


import logging

from mod_pywebsocket import msgutil


class StreamHixie75(object):
    """Stream of WebSocket messages."""

    def __init__(self, request):
        """Construct an instance.

        Args:
            request: mod_python request.
        """

        self._logger = logging.getLogger('mod_pywebsocket.stream_hixie75')

        self._request = request
        self._request.client_terminated = False
        self._request.server_terminated = False

    def send_message(self, message, end=True):
        """Send message.

        Args:
            message: unicode string to send.

        Raises:
            msgutil.BadOperationException: when called on a server-terminated
                connection.
        """

        if not end:
            raise msgutil.BadOperationException(
                'StreamHixie75 doesn\'t support send_message with end=False')

        if self._request.server_terminated:
            raise msgutil.BadOperationException(
                'Requested send_message after sending out a closing handshake')

        msgutil.write_better_exc(
            self._request, ''.join(['\x00', message.encode('utf-8'), '\xff']))

    def receive_message(self):
        """Receive a WebSocket frame and return its payload an unicode string.

        Returns:
            payload unicode string in a WebSocket frame.

        Raises:
            msgutil.ConnectionTerminatedException: when read returns empty
                string.
            msgutil.BadOperationException: when called on a client-terminated
                connection.
        """

        if self._request.client_terminated:
            raise msgutil.BadOperationException(
                'Requested receive_message after receiving a closing handshake')

        while True:
            # Read 1 byte.
            # mp_conn.read will block if no bytes are available.
            # Timeout is controlled by TimeOut directive of Apache.
            frame_type_str = msgutil.receive_bytes(self._request, 1)
            frame_type = ord(frame_type_str)
            if (frame_type & 0x80) == 0x80:
                # The payload length is specified in the frame.
                # Read and discard.
                length = msgutil.payload_length_hixie75(self._request)
                if length > 0:
                    _ = msgutil.receive_bytes(self._request, length)
                # 5.3 3. 12. if /type/ is 0xFF and /length/ is 0, then set the
                # /client terminated/ flag and abort these steps.
                if self._request.ws_version is msgutil.VERSION_HIXIE75:
                    continue

                if frame_type == 0xFF and length == 0:
                    self._request.client_terminated = True

                    if self._request.server_terminated:
                        self._logger.debug(
                            'Received ack for server-initiated closing '
                            'handshake')
                        return None

                    self._logger.debug(
                        'Received client-initiated closing handshake')

                    self._send_closing_handshake()
                    self._logger.debug(
                        'Sent ack for client-initiated closing handshake')
                    return None
            else:
                # The payload is delimited with \xff.
                bytes = msgutil.read_until(self._request, '\xff')
                # The Web Socket protocol section 4.4 specifies that invalid
                # characters must be replaced with U+fffd REPLACEMENT
                # CHARACTER.
                message = bytes.decode('utf-8', 'replace')
                if frame_type == 0x00:
                    return message
                # Discard data of other types.

    def _send_closing_handshake(self):
        self._request.server_terminated = True

        # 5.3 the server may decide to terminate the WebSocket connection by
        # running through the following steps:
        # 1. send a 0xFF byte and a 0x00 byte to the client to indicate the
        # start of the closing handshake.
        msgutil.write_better_exc(self._request, '\xff\x00')

    def close_connection(self):
        """Closes a WebSocket connection.

        Raises:
            msgutil.ConnectionTerminatedException: when closing handshake was
                not successfull.
        """

        if self._request.server_terminated:
            self._logger.debug(
                'Requested close_connection but server is already terminated')
            return

        if self._request.ws_version is msgutil.VERSION_HIXIE75:
            self._request.server_terminated = True
            self._logger.debug('Connection closed')
            return

        self._send_closing_handshake()
        self._logger.debug('Sent server-initiated closing handshake')

        # TODO(ukai): 2. wait until the /client terminated/ flag has been set,
        # or until a server-defined timeout expires.
        #
        # For now, we expect receiving closing handshake right after sending
        # out closing handshake, and if we couldn't receive non-handshake
        # frame, we take it as ConnectionTerminatedException.
        message = self.receive_message()
        if message is not None:
            raise msgutil.ConnectionTerminatedException(
                'Didn\'t receive valid ack for closing handshake')
        # TODO: 3. close the WebSocket connection.
        # note: mod_python Connection (mp_conn) doesn't have close method.

    def send_ping(self, body):
        raise msgutil.BadOperationException(
            'StreamHixie75 doesn\'t support send_ping')


# vi:sts=4 sw=4 et
