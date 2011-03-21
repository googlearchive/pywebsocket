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


"""Stream class for IETF HyBi 06 WebSocket protocol.
"""


from collections import deque
import struct

from mod_pywebsocket import common
from mod_pywebsocket import util
from mod_pywebsocket._stream_base import BadOperationException
from mod_pywebsocket._stream_base import ConnectionTerminatedException
from mod_pywebsocket._stream_base import InvalidFrameException
from mod_pywebsocket._stream_base import StreamBase
from mod_pywebsocket._stream_base import UnsupportedFrameException


def is_control_opcode(opcode):
    return (opcode == common.OPCODE_CLOSE or
            opcode == common.OPCODE_PING or
            opcode == common.OPCODE_PONG)


# Helper functions made public to be used for writing unittests for WebSocket
# clients.
def create_length_header(length, rsv4):
    """Creates a length header.

    Args:
        length: Frame length. Must be less than 2^63.
        rsv4: RSV4 bit. Must be 0 or 1.

    Raises:
        ValueError: when bad data is given.
    """

    if rsv4 & ~1:
        raise ValueError('rsv4 must be 0 or 1')

    header = ''

    if length < 0:
        raise ValueError('length must be non negative integer')
    elif length <= 125:
        second_byte = (rsv4 << 7) | length
        header += chr(second_byte)
    elif length < (1 << 16):
        second_byte = (rsv4 << 7) | 126
        header += chr(second_byte) + struct.pack('!H', length)
    elif length < (1 << 63):
        second_byte = (rsv4 << 7) | 127
        header += chr(second_byte) + struct.pack('!Q', length)
    else:
        raise ValueError('Payload is too big for one frame')

    return header


def create_header(opcode, payload_length, fin, rsv1, rsv2, rsv3, rsv4):
    """Creates a frame header.

    Raises:
        Exception: when bad data is given.
    """

    if opcode < 0 or 0xf < opcode:
        raise ValueError('Opcode out of range')

    if payload_length < 0 or (1 << 63) <= payload_length:
        raise ValueError('payload_length out of range')

    if (fin | rsv1 | rsv2 | rsv3 | rsv4) & ~1:
        raise ValueError('FIN bit and Reserved bit parameter must be 0 or 1')

    header = ''

    first_byte = ((fin << 7)
                  | (rsv1 << 6) | (rsv2 << 5) | (rsv3 << 4)
                  | opcode)
    header += chr(first_byte)
    header += create_length_header(payload_length, rsv4)

    return header


def create_text_frame(message, opcode=common.OPCODE_TEXT, fin=1):
    """Creates a simple text frame with no extension, reserved bit."""

    encoded_message = message.encode('utf-8')
    header = create_header(opcode, len(encoded_message), fin, 0, 0, 0, 0)
    return header + encoded_message


class FragmentedTextFrameBuilder(object):
    """A stateful class to send a message as fragments."""

    def __init__(self):
        """Constructs an instance."""

        self._started = False

    def build(self, message, end):
        if self._started:
            opcode = common.OPCODE_CONTINUATION
        else:
            opcode = common.OPCODE_TEXT

        if end:
            self._started = False
            fin = 1
        else:
            self._started = True
            fin = 0

        return create_text_frame(message, opcode, fin)


def create_ping_frame(body):
    header = create_header(common.OPCODE_PING, len(body), 1, 0, 0, 0, 0)
    return header + body


def create_pong_frame(body):
    header = create_header(common.OPCODE_PONG, len(body), 1, 0, 0, 0, 0)
    return header + body


def create_close_frame(body):
    header = create_header(common.OPCODE_CLOSE, len(body), 1, 0, 0, 0, 0)
    return header + body


class Stream(StreamBase):
    """Stream of WebSocket messages."""

    def __init__(self, request):
        """Construct an instance.

        Args:
            request: mod_python request.
        """

        StreamBase.__init__(self, request)

        self._logger = util.get_class_logger(self)

        if self._request.ws_deflate:
            self._logger.debug('Deflated stream')
            self._request = util.DeflateRequest(self._request)

        self._request.client_terminated = False
        self._request.server_terminated = False

        # Holds body of received fragments.
        self._received_fragments = []
        # Holds the opcode of the first fragment.
        self._original_opcode = None

        self._writer = FragmentedTextFrameBuilder()

        self._ping_queue = deque()

    def _receive_frame(self):
        """Receives a frame and return data in the frame as a tuple containing
        each header field and payload separately.

        Raises:
            ConnectionTerminatedException: when read returns empty
                string.
            InvalidFrameException: when the frame contains invalid data.
        """

        masking_nonce = self.receive_bytes(4)
        masker = util.RepeatedXorMasker(masking_nonce)

        received = masker.mask(self.receive_bytes(2))

        first_byte = ord(received[0])
        fin = (first_byte >> 7) & 1
        rsv1 = (first_byte >> 6) & 1
        rsv2 = (first_byte >> 5) & 1
        rsv3 = (first_byte >> 4) & 1
        opcode = first_byte & 0xf

        second_byte = ord(received[1])
        rsv4 = (second_byte >> 7) & 1
        payload_length = second_byte & 0x7f

        if payload_length == 127:
            extended_payload_length = masker.mask(self.receive_bytes(8))
            payload_length = struct.unpack(
                '!Q', extended_payload_length)[0]
            if payload_length > 0x7FFFFFFFFFFFFFFF:
                raise InvalidFrameException(
                    'Extended payload length >= 2^63')
        elif payload_length == 126:
            extended_payload_length = masker.mask(self.receive_bytes(2))
            payload_length = struct.unpack(
                '!H', extended_payload_length)[0]

        bytes = masker.mask(self.receive_bytes(payload_length))

        return opcode, bytes, fin, rsv1, rsv2, rsv3, rsv4

    def send_message(self, message, end=True):
        """Send message.

        Args:
            message: unicode string to send.

        Raises:
            BadOperationException: when called on a server-terminated
                connection.
        """

        if self._request.server_terminated:
            raise BadOperationException(
                'Requested send_message after sending out a closing handshake')

        self._write(self._writer.build(message, end))

    def receive_message(self):
        """Receive a WebSocket frame and return its payload an unicode string.

        Returns:
            payload unicode string in a WebSocket frame. None iff received
            closing handshake.
        Raises:
            BadOperationException: when called on a client-terminated
                connection.
            ConnectionTerminatedException: when read returns empty
                string.
            InvalidFrameException: when the frame contains invalid
                data.
            UnsupportedFrameException: when the received frame has
                flags, opcode we cannot handle. You can ignore this exception
                and continue receiving the next frame.
        """

        if self._request.client_terminated:
            raise BadOperationException(
                'Requested receive_message after receiving a closing handshake')

        while True:
            # mp_conn.read will block if no bytes are available.
            # Timeout is controlled by TimeOut directive of Apache.

            opcode, bytes, fin, rsv1, rsv2, rsv3, rsv4 = self._receive_frame()
            if rsv1 or rsv2 or rsv3 or rsv4:
                raise UnsupportedFrameException(
                    'Unsupported flag is set (rsv = %d%d%d%d)' %
                    (rsv1, rsv2, rsv3, rsv4))

            if opcode == common.OPCODE_CONTINUATION:
                if not self._received_fragments:
                    if fin:
                        raise InvalidFrameException(
                            'Received a termination frame but fragmentation '
                            'not started')
                    else:
                        raise InvalidFrameException(
                            'Received an intermediate frame but '
                            'fragmentation not started')

                if fin:
                    # End of fragmentation frame
                    self._received_fragments.append(bytes)
                    message = ''.join(self._received_fragments)
                    self._received_fragments = []
                else:
                    # Intermediate frame
                    self._received_fragments.append(bytes)
                    continue
            else:
                if self._received_fragments:
                    if fin:
                        raise InvalidFrameException(
                            'Received an unfragmented frame without '
                            'terminating existing fragmentation')
                    else:
                        raise InvalidFrameException(
                            'New fragmentation started without terminating '
                            'existing fragmentation')

                if fin:
                    # Unfragmented frame
                    self._original_opcode = opcode
                    message = bytes
                else:
                    # Start of fragmentation frame

                    if is_control_opcode(opcode):
                        raise InvalidFrameException(
                            'Control frames must not be fragmented')

                    self._original_opcode = opcode
                    self._received_fragments.append(bytes)
                    continue

            if self._original_opcode == common.OPCODE_TEXT:
                # The WebSocket protocol section 4.4 specifies that invalid
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
                    raise InvalidFrameException(
                        'No ping waiting for pong on our queue')
                expected_body = self._ping_queue.popleft()
                if expected_body != message:
                    raise InvalidFrameException(
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
                raise UnsupportedFrameException(
                    'opcode %d is not supported' % self._original_opcode)

    def _send_closing_handshake(self):
        self._request.server_terminated = True

        frame = create_close_frame('')
        self._write(frame)

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
            raise ConnectionTerminatedException(
                'Didn\'t receive valid ack for closing handshake')
        # TODO: 3. close the WebSocket connection.
        # note: mod_python Connection (mp_conn) doesn't have close method.

    def send_ping(self, body=''):
        frame = create_ping_frame(body)
        self._write(frame)

        self._ping_queue.append(body)

    def _send_pong(self, body):
        frame = create_pong_frame(body)
        self._write(frame)


# vi:sts=4 sw=4 et
