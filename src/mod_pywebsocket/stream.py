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


"""Stream of WebSocket protocol with the framing introduced by IETF HyBi 01.
"""


from collections import deque
import logging
import struct

from mod_pywebsocket import common
from mod_pywebsocket import msgutil
from mod_pywebsocket import util


def receive_frame(request):
    """Receives a frame and return data in the frame as a tuple containing
    each header field and payload separately.

    Raises:
        msgutil.ConnectionTerminatedException: when read returns empty
            string.
        msgutil.InvalidFrameException: when the frame contains invalid data.
    """
    received = msgutil.receive_bytes(request, 2)

    first_byte = ord(received[0])
    more = first_byte >> 7 & 1
    rsv1 = first_byte >> 6 & 1
    rsv2 = first_byte >> 5 & 1
    rsv3 = first_byte >> 4 & 1
    opcode = first_byte & 0xf

    second_byte = ord(received[1])
    rsv4 = second_byte >> 7 & 1
    payload_length = second_byte & 0x7f

    if payload_length == 127:
        extended_payload_length = msgutil.receive_bytes(request, 8)
        payload_length = struct.unpack(
            '!Q', extended_payload_length)[0]
        if payload_length > 0x7FFFFFFFFFFFFFFF:
            raise msgutil.InvalidFrameException(
                'Extended payload length >= 2^63')
    elif payload_length == 126:
        extended_payload_length = msgutil.receive_bytes(request, 2)
        payload_length = struct.unpack(
            '!H', extended_payload_length)[0]

    bytes = msgutil.receive_bytes(request, payload_length)

    return opcode, bytes, more, rsv1, rsv2, rsv3, rsv4


class Stream(object):
    """Stream of WebSocket messages."""

    def __init__(self, request):
        """Construct an instance.

        Args:
            request: mod_python request.
        """

        self._logger = util.get_class_logger(self)

        self._request = request
        self._request.client_terminated = False
        self._request.server_terminated = False

        # Holds body of received fragments.
        self._received_fragments = []
        # Holds the opcode of the first fragment.
        self._original_opcode = None

        self._writer = msgutil.FragmentedTextFrameBuilder()

        self._ping_queue = deque()

    def send_message(self, message, end=True):
        """Send message.

        Args:
            message: unicode string to send.

        Raises:
            msgutil.BadOperationException: when called on a server-terminated
                connection.
        """

        if self._request.server_terminated:
            raise msgutil.BadOperationException(
                'Requested send_message after sending out a closing handshake')

        msgutil.write_better_exc(
            self._request, self._writer.build(message, end))

    def receive_message(self):
        """Receive a WebSocket frame and return its payload an unicode string.

        Returns:
            payload unicode string in a WebSocket frame. None iff received
            closing handshake.
        Raises:
            msgutil.BadOperationException: when called on a client-terminated
                connection.
            msgutil.ConnectionTerminatedException: when read returns empty
                string.
            msgutil.InvalidFrameException: when the frame contains invalid
                data.
            msgutil.UnsupportedFrameException: when the received frame has
                flags, opcode we cannot handle. You can ignore this exception
                and continue receiving the next frame.
        """

        if self._request.client_terminated:
            raise msgutil.BadOperationException(
                'Requested receive_message after receiving a closing handshake')

        while True:
            # mp_conn.read will block if no bytes are available.
            # Timeout is controlled by TimeOut directive of Apache.

            opcode, bytes, more, rsv1, rsv2, rsv3, rsv4 = receive_frame(
                self._request)
            if rsv1 or rsv2 or rsv3 or rsv4:
                raise msgutil.UnsupportedFrameException(
                    'Unsupported flag is set (rsv = %d%d%d%d)' %
                    (rsv1, rsv2, rsv3, rsv4))

            if opcode == common.OPCODE_CONTINUATION:
                if not self._received_fragments:
                    if more:
                        raise msgutil.InvalidFrameException(
                            'Received an intermediate frame but '
                            'fragmentation not started')
                    else:
                        raise msgutil.InvalidFrameException(
                            'Received a termination frame but fragmentation '
                            'not started')

                if more:
                    # Intermediate frame
                    self._received_fragments.append(bytes)
                    continue
                else:
                    # End of fragmentation frame
                    self._received_fragments.append(bytes)
                    message = ''.join(self._received_fragments)
                    self._received_fragments = []
            else:
                if self._received_fragments:
                    if more:
                        raise msgutil.InvalidFrameException(
                            'New fragmentation started without terminating '
                            'existing fragmentation')
                    else:
                        raise msgutil.InvalidFrameException(
                            'Received an unfragmented frame without '
                            'terminating existing fragmentation')

                if more:
                    # Start of fragmentation frame

                    if msgutil.is_control_opcode(opcode):
                        raise msgutil.InvalidFrameException(
                            'Control frames must not be fragmented')

                    self._original_opcode = opcode
                    self._received_fragments.append(bytes)
                    continue
                else:
                    # Unfragmented frame
                    self._original_opcode = opcode
                    message = bytes

            if self._original_opcode == common.OPCODE_TEXT:
                # The Web Socket protocol section 4.4 specifies that invalid
                # characters must be replaced with U+fffd REPLACEMENT
                # CHARACTER.
                return message.decode('utf-8', 'replace')
            elif self._original_opcode == common.OPCODE_CLOSE:
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
            elif self._original_opcode == common.OPCODE_PING:
                try:
                    handler = self._request.on_ping_handler
                    if handler:
                        handler(self._request, message)
                        continue
                except AttributeError, e:
                    pass
                self._send_pong(message)
            elif self._original_opcode == common.OPCODE_PONG:
                # TODO(tyoshino): Add ping timeout handling.

                if len(self._ping_queue) == 0:
                    raise msgutil.InvalidFrameException(
                        'No ping waiting for pong on our queue')
                expected_body = self._ping_queue.popleft()
                if expected_body != message:
                    raise msgutil.InvalidFrameException(
                        'Received pong contained a body different from our '
                        'ping\'s one')

                try:
                    handler = self._request.on_pong_handler
                    if handler:
                        handler(self._request, message)
                        continue
                except AttributeError, e:
                    pass

                continue
            else:
                raise msgutil.UnsupportedFrameException(
                    'opcode %d is not supported' % self._original_opcode)

    def _send_closing_handshake(self):
        self._request.server_terminated = True

        frame = msgutil.create_close_frame('')
        msgutil.write_better_exc(self._request, frame)

    def close_connection(self):
        """Closes a WebSocket connection."""

        if self._request.server_terminated:
            self._logger.debug(
                'Requested close_connection but server is already terminated')
            return

        self._send_closing_handshake()
        self._logger.debug('Sent server-initiated closing handshake')

        # TODO(ukai): 2. wait until the /client terminated/ flag has been set,
        # or until a server-defined timeout expires.
        #
        # For now, we expect receiving closing handshake right after sending
        # out closing handshake.
        message = self.receive_message()
        if message is not None:
            raise msgutil.ConnectionTerminatedException(
                'Didn\'t receive valid ack for closing handshake')
        # TODO: 3. close the WebSocket connection.
        # note: mod_python Connection (mp_conn) doesn't have close method.

    def send_ping(self, body=''):
        frame = msgutil.create_ping_frame(body)
        msgutil.write_better_exc(self._request, frame)

        self._ping_queue.append(body)

    def _send_pong(self, body):
        frame = msgutil.create_pong_frame(body)
        msgutil.write_better_exc(self._request, frame)


# vi:sts=4 sw=4 et
