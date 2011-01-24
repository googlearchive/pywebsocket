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


"""Message related utilities.

Note: request.connection.write/read are used in this module, even though
mod_python document says that they should be used only in connection handlers.
Unfortunately, we have no other options. For example, request.write/read are
not suitable because they don't allow direct raw bytes writing/reading.
"""


import Queue
import struct
import threading

from mod_pywebsocket import common
from mod_pywebsocket import util


# Exceptions
class ConnectionTerminatedException(Exception):
    """This exception will be raised when a connection is terminated
    unexpectedly.
    """
    pass


class InvalidFrameException(ConnectionTerminatedException):
    """This exception will be raised when we received an invalid frame we
    cannot parse.
    """
    pass


class BadOperationException(RuntimeError):
    """This exception will be raised when send_message() is called on
    server-terminated connection or receive_message() is called on
    client-terminated connection.
    """
    pass


class UnsupportedFrameException(RuntimeError):
    """This exception will be raised when we receive a frame with flag, opcode
    we cannot handle. Handlers can just catch and ignore this exception and
    call receive_message() again to continue processing the next frame.
    """
    pass


def is_control_opcode(opcode):
    return (opcode == common.OPCODE_CLOSE or
            opcode == common.OPCODE_PING or
            opcode == common.OPCODE_PONG)


def read_better_exc(request, length):
    """Reads length bytes from connection. In case we catch any exception,
    prepends remote address to the exception message and raise again.

    Raises:
        ConnectionTerminatedException: when read returns empty string.
    """

    bytes = request.connection.read(length)
    if not bytes:
        raise ConnectionTerminatedException(
            'Receiving %d byte failed. Peer (%r) closed connection' %
            (length, (request.connection.remote_addr,)))
    return bytes


def write_better_exc(request, bytes):
    """Writes given bytes to connection. In case we catch any exception,
    prepends remote address to the exception message and raise again.
    """

    try:
        request.connection.write(bytes)
    except Exception, e:
        util.prepend_message_to_exception(
                'Failed to send message to %r: ' %
                        (request.connection.remote_addr,),
                e)
        raise


def receive_bytes(request, length):
    """Receives multiple bytes. Retries read when we couldn't receive the
    specified amount.

    Raises:
        ConnectionTerminatedException: when read returns empty string.
    """

    bytes = []
    while length > 0:
        new_bytes = read_better_exc(request, length)
        bytes.append(new_bytes)
        length -= len(new_bytes)
    return ''.join(bytes)


def read_until(request, delim_char):
    """Reads bytes until we encounter delim_char. The result will not contain
    delim_char.

    Raises:
        ConnectionTerminatedException: when read returns empty string.
    """

    bytes = []
    while True:
        ch = read_better_exc(request, 1)
        if ch == delim_char:
            break
        bytes.append(ch)
    return ''.join(bytes)


# An API for handler to send/receive WebSocket messages.
def close_connection(request):
    """Close connection.

    Args:
        request: mod_python request.
    """
    request.ws_stream.close_connection()


def send_message(request, message, end=True):
    """Send message.

    Args:
        request: mod_python request.
        message: unicode string to send.
        end: False to send message as a fragment. All messages until the first
             call with end=True (inclusive) will be delivered to the client
             in separate frames but as one WebSocket message.
    Raises:
        BadOperationException: when server already terminated.
    """
    request.ws_stream.send_message(message, end)


def receive_message(request):
    """Receive a Web Socket frame and return its payload as unicode string.

    Args:
        request: mod_python request.
    Raises:
        BadOperationException: when client already terminated.
    """
    return request.ws_stream.receive_message()


def send_ping(request, body=''):
    request.ws_stream.send_ping(body)


# Helper functions made public to be used for writing unittests for WebSocket
# clients.
def create_length_header(length, rsv4):
    """Creates a length header.

    Raises:
        ValueError: when bad data is given.
    """

    if rsv4 != 0 and rsv4 != 1:
        raise ValueError('rsv4 must be 0 or 1')

    header = ''

    if length <= 125:
        second_byte = rsv4 << 7 | length
        header += chr(second_byte)
    elif length < 1 << 16:
        second_byte = rsv4 << 7 | 126
        header += chr(second_byte) + struct.pack('!H', length)
    elif length < 1 << 63:
        second_byte = rsv4 << 7 | 127
        header += chr(second_byte) + struct.pack('!Q', length)
    else:
        raise ValueError('Payload is too big for one frame')

    return header


def create_header(opcode, payload_length, more, rsv1, rsv2, rsv3, rsv4):
    """Creates a frame header.

    Raises:
        Exception: when bad data is given.
    """

    if opcode < 0 or 0xf < opcode:
        raise ValueError('Opcode out of range')

    if payload_length < 0 or 1 << 63 <= payload_length:
        raise ValueError('payload_length out of range')

    if (more | rsv1 | rsv2 | rsv3 | rsv4) & ~1:
        raise ValueError('Reserved bit parameter must be 0 or 1')

    header = ''

    first_byte = (more << 7
                  | rsv1 << 6 | rsv2 << 5 | rsv3 << 4
                  | opcode)
    header += chr(first_byte)
    header += create_length_header(payload_length, rsv4)

    return header


def create_text_frame(message, opcode=common.OPCODE_TEXT, more=0):
    """Creates a simple text frame with no extension, reserved bit."""

    encoded_message = message.encode('utf-8')
    header = create_header(opcode, len(encoded_message), more, 0, 0, 0, 0)
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
            more = 0
        else:
            self._started = True
            more = 1

        return create_text_frame(message, opcode, more)


def create_ping_frame(body):
    header = create_header(common.OPCODE_PING, len(body), 0, 0, 0, 0, 0)
    return header + body


def create_pong_frame(body):
    header = create_header(common.OPCODE_PONG, len(body), 0, 0, 0, 0, 0)
    return header + body


def create_close_frame(body):
    header = create_header(common.OPCODE_CLOSE, len(body), 0, 0, 0, 0, 0)
    return header + body


# Helper functions for Hixie75
def payload_length_hixie75(request):
    """Reads a length header in a Hixie75 version frame with length.

    Raises:
        ConnectionTerminatedException: when read returns empty string.
    """

    length = 0
    while True:
        b_str = read_better_exc(request, 1)
        b = ord(b_str)
        length = length * 128 + (b & 0x7f)
        if (b & 0x80) == 0:
            break
    return length


class MessageReceiver(threading.Thread):
    """This class receives messages from the client.

    This class provides three ways to receive messages: blocking, non-blocking,
    and via callback. Callback has the highest precedence.

    Note: This class should not be used with the standalone server for wss
    because pyOpenSSL used by the server raises a fatal error if the socket
    is accessed from multiple threads.
    """
    def __init__(self, request, onmessage=None):
        """Construct an instance.

        Args:
            request: mod_python request.
            onmessage: a function to be called when a message is received.
                       May be None. If not None, the function is called on
                       another thread. In that case, MessageReceiver.receive
                       and MessageReceiver.receive_nowait are useless because
                       they will never return any messages.
        """
        threading.Thread.__init__(self)
        self._request = request
        self._queue = Queue.Queue()
        self._onmessage = onmessage
        self._stop_requested = False
        self.setDaemon(True)
        self.start()

    def run(self):
        try:
            while not self._stop_requested:
                message = receive_message(self._request)
                if self._onmessage:
                    self._onmessage(message)
                else:
                    self._queue.put(message)
        finally:
            close_connection(self._request)

    def receive(self):
        """ Receive a message from the channel, blocking.

        Returns:
            message as a unicode string.
        """
        return self._queue.get()

    def receive_nowait(self):
        """ Receive a message from the channel, non-blocking.

        Returns:
            message as a unicode string if available. None otherwise.
        """
        try:
            message = self._queue.get_nowait()
        except Queue.Empty:
            message = None
        return message

    def stop(self):
        """Request to stop this instance.

        The instance will be stopped after receiving the next message.
        This method may not be very useful, but there is no clean way
        in Python to forcefully stop a running thread.
        """
        self._stop_requested = True


class MessageSender(threading.Thread):
    """This class sends messages to the client.

    This class provides both synchronous and asynchronous ways to send
    messages.

    Note: This class should not be used with the standalone server for wss
    because pyOpenSSL used by the server raises a fatal error if the socket
    is accessed from multiple threads.
    """
    def __init__(self, request):
        """Construct an instance.

        Args:
            request: mod_python request.
        """
        threading.Thread.__init__(self)
        self._request = request
        self._queue = Queue.Queue()
        self.setDaemon(True)
        self.start()

    def run(self):
        while True:
            message, condition = self._queue.get()
            condition.acquire()
            send_message(self._request, message)
            condition.notify()
            condition.release()

    def send(self, message):
        """Send a message, blocking."""

        condition = threading.Condition()
        condition.acquire()
        self._queue.put((message, condition))
        condition.wait()

    def send_nowait(self, message):
        """Send a message, non-blocking."""

        self._queue.put((message, threading.Condition()))


# vi:sts=4 sw=4 et
