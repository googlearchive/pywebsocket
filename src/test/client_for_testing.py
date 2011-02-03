#!/usr/bin/env python
#
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


"""WebSocket client utility for testing.

This module contains helper methods for performing handshake, frame
sending/receiving as a WebSocket client.

This is code for testing mod_pywebsocket. Keep this code independent from
mod_pywebsocket. Don't import e.g. Stream class for generating frame for
testing. Using util.hexify, etc. that are not related to protocol processing
is allowed.

Note:
This code is far from robust, e.g., we cut corners in handshake.
"""


# Use md5 module in Python 2.4
try:
    import hashlib
    md5_hash = hashlib.md5
except ImportError:
    import md5
    md5_hash = md5.md5

import logging
import random
import re
import socket
import struct

from mod_pywebsocket import util


_DEFAULT_PORT = 80
_DEFAULT_SECURE_PORT = 443

# Opcodes introduced in IETF HyBi 01 for the new framing format
_OPCODE_CONTINUATION = 0x0
_OPCODE_CLOSE        = 0x1
_OPCODE_TEXT         = 0x4

# Strings used for handshake
_UPGRADE_HEADER = 'Upgrade: WebSocket\r\n'
_CONNECTION_HEADER = 'Connection: Upgrade\r\n'


def _method_line(resource):
    return 'GET %s HTTP/1.1\r\n' % resource


def _origin_header(origin):
    # 4.1 13. concatenation of the string "Origin:", a U+0020 SPACE character,
    # and the /origin/ value, converted to ASCII lowercase, to /fields/.
    return 'Origin: %s\r\n' % origin.lower()


def _format_host_header(host, port, secure):
    # 4.1 9. Let /hostport/ be an empty string.
    # 4.1 10. Append the /host/ value, converted to ASCII lowercase, to
    # /hostport/
    hostport = host.lower()
    # 4.1 11. If /secure/ is false, and /port/ is not 80, or if /secure/
    # is true, and /port/ is not 443, then append a U+003A COLON character
    # (:) followed by the value of /port/, expressed as a base-ten integer,
    # to /hostport/
    if ((not secure and port != _DEFAULT_PORT) or
        (secure and port != _DEFAULT_SECURE_PORT)):
        hostport += ':' + str(port)
    # 4.1 12. concatenation of the string "Host:", a U+0020 SPACE
    # character, and /hostport/, to /fields/.
    return 'Host: ' + hostport + '\r\n'


def _receive_bytes(socket, length):
    bytes = []
    while length > 0:
        new_bytes = socket.recv(length)
        if not new_bytes:
            raise Exception('connection closed unexpectedly')
        bytes.append(new_bytes)
        length -= len(new_bytes)
    return ''.join(bytes)


def _send_bytes(socket, bytes):
    pos = 0
    size = len(bytes)
    while pos < size:
        nbytes = socket.send(bytes[pos:])
        pos += nbytes


class _TLSSocket(object):
    """Wrapper for a TLS connection."""

    def __init__(self, raw_socket):
        self._ssl = socket.ssl(raw_socket)

    def send(self, bytes):
        return self._ssl.write(bytes)

    def recv(self, size=-1):
        return self._ssl.read(size)

    def close(self):
        # Nothing to do.
        pass


class WebSocketHybi00Handshake(object):
    """WebSocket handshake processor for IETF HyBi 00 and later."""

    def __init__(self, options, draft_field):
        self._logger = util.get_class_logger(self)

        self._options = options
        self._draft_field = draft_field

    def handshake(self, socket):
        """Handshake WebSocket.

        Raises:
            Exception: handshake failed.
        """

        self._socket = socket

        # 4.1 5. send request line.
        _send_bytes(self._socket, _method_line(self._options.resource))
        # 4.1 6. Let /fields/ be an empty list of strings.
        fields = []
        # 4.1 7. Add the string "Upgrade: WebSocket" to /fields/.
        fields.append(_UPGRADE_HEADER)
        # 4.1 8. Add the string "Connection: Upgrade" to /fields/.
        fields.append(_CONNECTION_HEADER)
        # 4.1 9-12. Add Host: field to /fields/.
        fields.append(_format_host_header(
            self._options.server_host,
            self._options.server_port,
            self._options.use_tls))
        # 4.1 13. Add Origin: field to /fields/.
        fields.append(_origin_header(self._options.origin))
        # TODO: 4.1 14 Add Sec-WebSocket-Protocol: field to /fields/.
        # TODO: 4.1 15 Add cookie headers to /fields/.

        # 4.1 16-23. Add Sec-WebSocket-Key<n> to /fields/.
        self._number1, key1 = self._generate_sec_websocket_key()
        fields.append('Sec-WebSocket-Key1: ' + key1 + '\r\n')
        self._number2, key2 = self._generate_sec_websocket_key()
        fields.append('Sec-WebSocket-Key2: ' + key2 + '\r\n')

        fields.append('Sec-WebSocket-Draft: %s\r\n' % self._draft_field)

        # 4.1 24. For each string in /fields/, in a random order: send the
        # string, encoded as UTF-8, followed by a UTF-8 encoded U+000D CARRIAGE
        # RETURN U+000A LINE FEED character pair (CRLF).
        random.shuffle(fields)
        for field in fields:
            _send_bytes(self._socket, field)
        # 4.1 25. send a UTF-8-encoded U+000D CARRIAGE RETURN U+000A LINE FEED
        # character pair (CRLF).
        _send_bytes(self._socket, '\r\n')
        # 4.1 26. let /key3/ be a string consisting of eight random bytes (or
        # equivalently, a random 64 bit integer encoded in a big-endian order).
        self._key3 = self._generate_key3()
        # 4.1 27. send /key3/ to the server.
        _send_bytes(self._socket, self._key3)

        self._logger.info('Sent handshake')

        # 4.1 28. Read bytes from the server until either the connection closes,
        # or a 0x0A byte is read. let /field/ be these bytes, including the 0x0A
        # bytes.
        field = ''
        while True:
            ch = _receive_bytes(self._socket, 1)
            field += ch
            if ch == '\n':
                break
        # if /field/ is not at least seven bytes long, or if the last
        # two bytes aren't 0x0D and 0x0A respectively, or if it does not
        # contain at least two 0x20 bytes, then fail the WebSocket connection
        # and abort these steps.
        if len(field) < 7 or not field.endswith('\r\n'):
            raise Exception('wrong status line: %s' % field)
        m = re.match('[^ ]* ([^ ]*) .*', field)
        if m is None:
            raise Exception('no code found in: %s' % field)
        # 4.1 29. let /code/ be the substring of /field/ that starts from the
        # byte after the first 0x20 byte, and ends with the byte before the
        # second 0x20 byte.
        code = m.group(1)
        # 4.1 30. if /code/ is not three bytes long, or if any of the bytes in
        # /code/ are not in the range 0x30 to 0x90, then fail the WebSocket
        # connection and abort these steps.
        if not re.match('[0-9][0-9][0-9]', code):
            raise Exception('wrong code %s in: %s' % (code, field))
        # 4.1 31. if /code/, interpreted as UTF-8, is "101", then move to the
        # next step.
        if code != '101':
            raise Exception('unexpected code in: %s' % field)
        # 4.1 32-39. read fields into /fields/
        fields = self._read_fields()
        # 4.1 40. _Fields processing_
        # read a byte from server
        ch = _receive_bytes(self._socket, 1)
        if ch != '\n':  # 0x0A
            raise Exception('expected LF after line: %s: %s' % (name, value))
        # 4.1 41. check /fields/
        if len(fields['upgrade']) != 1:
            raise Exception('not one ugprade: %s' % fields['upgrade'])
        if len(fields['connection']) != 1:
            raise Exception('not one connection: %s' % fields['connection'])
        if len(fields['sec-websocket-origin']) != 1:
            raise Exception('not one sec-websocket-origin: %s' %
                            fields['sec-sebsocket-origin'])
        if len(fields['sec-websocket-location']) != 1:
            raise Exception('not one sec-websocket-location: %s' %
                            fields['sec-sebsocket-location'])
        # TODO(ukai): protocol
        # if the entry's name is "upgrade"
        #  if the value is not exactly equal to the string "WebSocket",
        #  then fail the WebSocket connection and abort these steps.
        if fields['upgrade'][0] != 'WebSocket':
            raise Exception('unexpected upgrade: %s' % fields['upgrade'][0])
        # if the entry's name is "connection"
        #  if the value, converted to ASCII lowercase, is not exactly equal
        #  to the string "upgrade", then fail the WebSocket connection and
        #  abort these steps.
        if fields['connection'][0].lower() != 'upgrade':
            raise Exception('unexpected connection: %s' %
                            fields['connection'][0])
        # TODO(ukai): check origin, location, cookie, ..

        # 4.1 42. let /challenge/ be the concatenation of /number_1/,
        # expressed as a big endian 32 bit integer, /number_2/, expressed
        # as big endian 32 bit integer, and the eight bytes of /key_3/ in the
        # order they were sent on the wire.
        challenge = struct.pack('!I', self._number1)
        challenge += struct.pack('!I', self._number2)
        challenge += self._key3

        self._logger.debug('num %d, %d, %s' % (
            self._number1, self._number2,
            util.hexify(self._key3)))
        self._logger.debug('challenge: %s' % util.hexify(challenge))

        # 4.1 43. let /expected/ be the MD5 fingerprint of /challenge/ as a
        # big-endian 128 bit string.
        expected = md5_hash(challenge).digest()
        self._logger.debug('expected : %s' % util.hexify(expected))

        # 4.1 44. read sixteen bytes from the server.
        # let /reply/ be those bytes.
        reply = _receive_bytes(self._socket, 16)
        self._logger.debug('reply    : %s' % util.hexify(reply))

        # 4.1 45. if /reply/ does not exactly equal /expected/, then fail
        # the WebSocket connection and abort these steps.
        if expected != reply:
            raise Exception('challenge/response failed: %s != %s' % (
                expected, reply))
        # 4.1 46. The *WebSocket connection is established*.

    def _generate_sec_websocket_key(self):
        # 4.1 16. let /spaces_n/ be a random integer from 1 to 12 inclusive.
        spaces = random.randint(1, 12)
        # 4.1 17. let /max_n/ be the largest integer not greater than
        #  4,294,967,295 divided by /spaces_n/.
        maxnum = 4294967295 / spaces
        # 4.1 18. let /number_n/ be a random integer from 0 to /max_n/
        # inclusive.
        number = random.randint(0, maxnum)
        # 4.1 19. let /product_n/ be the result of multiplying /number_n/ and
        # /spaces_n/ together.
        product = number * spaces
        # 4.1 20. let /key_n/ be a string consisting of /product_n/, expressed
        # in base ten using the numerals in the range U+0030 DIGIT ZERO (0) to
        # U+0039 DIGIT NINE (9).
        key = str(product)
        # 4.1 21. insert between one and twelve random characters from the
        # range U+0021 to U+002F and U+003A to U+007E into /key_n/ at random
        # positions.
        available_chars = range(0x21, 0x2f + 1) + range(0x3a, 0x7e + 1)
        n = random.randint(1, 12)
        for _ in xrange(n):
            ch = random.choice(available_chars)
            pos = random.randint(0, len(key))
            key = key[0:pos] + chr(ch) + key[pos:]
        # 4.1 22. insert /spaces_n/ U+0020 SPACE characters into /key_n/ at
        # random positions other than start or end of the string.
        for _ in xrange(spaces):
            pos = random.randint(1, len(key) - 1)
            key = key[0:pos] + ' ' + key[pos:]
        return number, key

    def _generate_key3(self):
        # 4.1 26. let /key3/ be a string consisting of eight random bytes (or
        # equivalently, a random 64 bit integer encoded in a big-endian order).
        return ''.join([chr(random.randint(0, 255)) for _ in xrange(8)])

    def _read_fields(self):
        # 4.1 32. let /fields/ be a list of name-value pairs, initially empty.
        fields = {}
        while True:  # "Field"
            # 4.1 33. let /name/ and /value/ be empty byte arrays
            name = ''
            value = ''
            # 4.1 34. read /name/
            name = self._read_name()
            if name is None:
                break
            # 4.1 35. read spaces
            # TODO(tyoshino): Skip only one space as described in the spec.
            ch = self._skip_spaces()
            # 4.1 36. read /value/
            value = self._read_value(ch)
            # 4.1 37. read a byte from the server
            ch = _receive_bytes(self._socket, 1)
            if ch != '\n':  # 0x0A
                raise Exception('expected LF after line: %s: %s' % (
                    name, value))
            # 4.1 38. append an entry to the /fields/ list that has the name
            # given by the string obtained by interpreting the /name/ byte
            # array as a UTF-8 stream and the value given by the string
            # obtained by interpreting the /value/ byte array as a UTF-8 byte
            # stream.
            fields.setdefault(name, []).append(value)
            # 4.1 39. return to the "Field" step above
        return fields

    def _read_name(self):
        # 4.1 33. let /name/ be empty byte arrays
        name = ''
        while True:
            # 4.1 34. read a byte from the server
            ch = _receive_bytes(self._socket, 1)
            if ch == '\r':  # 0x0D
                return None
            elif ch == '\n':  # 0x0A
                raise Exception(
                    'unexpected LF when reading header name (%r)' % name)
            elif ch == ':':  # 0x3A
                return name
            elif ch >= 'A' and ch <= 'Z':  # range 0x31 to 0x5A
                ch = chr(ord(ch) + 0x20)
                name += ch
            else:
                name += ch

    def _skip_spaces(self):
        # 4.1 35. read a byte from the server
        while True:
            ch = _receive_bytes(self._socket, 1)
            if ch == ' ':  # 0x20
                continue
            return ch

    def _read_value(self, ch):
        # 4.1 33. let /value/ be empty byte arrays
        value = ''
        # 4.1 36. read a byte from server.
        while True:
            if ch == '\r':  # 0x0D
                return value
            elif ch == '\n':  # 0x0A
                raise Exception(
                    'unexpected LF when reading header value (%r)' % value)
            else:
                value += ch
            ch = _receive_bytes(self._socket, 1)


class WebSocketHixie75Handshake(object):
    """WebSocket handshake processor for IETF Hixie 75."""

    _EXPECTED_RESPONSE = (
        'HTTP/1.1 101 Web Socket Protocol Handshake\r\n' +
        _UPGRADE_HEADER +
        _CONNECTION_HEADER)

    def __init__(self, options):
        self._logger = util.get_class_logger(self)

        self._options = options

    def _skip_headers(self):
        terminator = '\r\n\r\n'
        pos = 0
        while pos < len(terminator):
            received = _receive_bytes(self._socket, 1)
            if received == terminator[pos]:
                pos += 1
            elif received == terminator[0]:
                pos = 1
            else:
                pos = 0

    def handshake(self, socket):
        self._socket = socket

        _send_bytes(self._socket, _method_line(self._options.resource))
        _send_bytes(self._socket, _UPGRADE_HEADER)
        _send_bytes(self._socket, _CONNECTION_HEADER)
        _send_bytes(self._socket, _format_host_header(
            self._options.server_host,
            self._options.server_port,
            self._options.use_tls))
        _send_bytes(self._socket, _origin_header(self._options.origin))
        _send_bytes(self._socket, '\r\n')

        self._logger.info('Sent handshake')

        for expected_char in WebSocketHixie75Handshake._EXPECTED_RESPONSE:
            received = _receive_bytes(self._socket, 1)
            if expected_char != received:
                raise Exception('Handshake failure')
        # We cut corners and skip other headers.
        self._skip_headers()


class WebSocketStream(object):
    """WebSocket frame processor for IETF HyBi 00 or later."""

    _CLOSE_FRAME = chr(_OPCODE_CLOSE) + '\x00'

    def __init__(self, socket):
        self._socket = socket

        self._fragmented = False

    def send_text(self, payload, end=True):
        encoded_payload = payload.encode('utf-8')

        if self._fragmented:
            first_byte = _OPCODE_CONTINUATION
        else:
            first_byte = _OPCODE_TEXT

        if end:
            self._fragmented = False
        else:
            self._fragmented = True
            first_byte |= 0x80

        header = chr(first_byte)
        payload_length = len(encoded_payload)
        if payload_length <= 125:
            header += chr(payload_length)
        elif payload_length < 1 << 16:
            header += chr(126) + struct.pack('!H', payload_length)
        elif payload_length < 1 << 63:
            header += chr(127) + struct.pack('!Q', payload_length)
        else:
            raise Exception('Too long payload (%d byte)' % payload_length)
        _send_bytes(self._socket, header + encoded_payload)

    def assert_receive_text(self, payload, opcode=_OPCODE_TEXT, more=0,
                            rsv1=0, rsv2=0, rsv3=0, rsv4=0):
        received = _receive_bytes(self._socket, 2)

        first_byte = ord(received[0])
        actual_more = first_byte >> 7 & 1
        actual_rsv1 = first_byte >> 6 & 1
        actual_rsv2 = first_byte >> 5 & 1
        actual_rsv3 = first_byte >> 4 & 1
        actual_opcode = first_byte & 0xf

        if actual_opcode != opcode:
            raise Exception(
                'Unexpected opcode : %d (expected) vs %d (actual)' %
                (opcode, actual_opcode))

        if actual_more != more:
            raise Exception(
                'Unexpected more : %d (expected) vs %d (actual)' %
                (more, actual_more))

        second_byte = ord(received[1])
        actual_rsv4 = second_byte >> 7 & 1
        payload_length = second_byte & 0x7f

        actual_rsv = (actual_rsv1, actual_rsv2, actual_rsv3, actual_rsv4)
        rsv = (rsv1, rsv2, rsv3, rsv4)

        if actual_rsv != rsv:
            raise Exception(
                'Unexpected rsv : %r (expected) vs %r (actual)' %
                (rsv, actual_rsv))

        if payload_length == 127:
            extended_payload_length = _receive_bytes(self._socket, 8)
            payload_length = struct.unpack(
                '!Q', extended_payload_length)[0]
            if payload_length > 0x7FFFFFFFFFFFFFFF:
                raise Exception('Extended payload length >= 2^63')
        elif payload_length == 126:
            extended_payload_length = _receive_bytes(self._socket, 2)
            payload_length = struct.unpack(
                '!H', extended_payload_length)[0]

        if payload_length != len(payload):
            raise Exception(
                'Unexpected payload length : %d (expected) vs %d (actual)' %
                (payload_length, len(payload)))

        received = _receive_bytes(self._socket, payload_length)

        if payload != received:
            raise Exception(
                'Unexpected payload : %r (expected) vs %r (actual)' %
                (payload, data))

    def send_close(self):
        _send_bytes(self._socket, self._CLOSE_FRAME)

    def assert_receive_close(self):
        closing = _receive_bytes(self._socket, len(self._CLOSE_FRAME))
        if closing != self._CLOSE_FRAME:
            raise Exception('Didn\'t receive closing handshake')


class WebSocketStreamHixie75(object):
    """WebSocket frame processor for Hixie 75 and IETF HyBi 00."""

    _CLOSE_FRAME = '\xff\x00'

    def __init__(self, socket):
        self._socket = socket

    def send_text(self, payload, unused_end):
        encoded_payload = payload.encode('utf-8')
        frame = ''.join(['\x00', encoded_payload, '\xff'])
        _send_bytes(self._socket, frame)

    def assert_receive_text(self, payload):
        received = _receive_bytes(self._socket, 1)

        if received != '\x00':
            raise Exception(
                'Unexpected frame type : %d (expected) vs %d (actual)' %
                (0, ord(received)))

        received = _receive_bytes(self._socket, len(payload) + 1)
        if received[-1] != '\xff':
            raise Exception(
                'Termination expected : 0xff (expected) vs %r (actual)' %
                received)

        if received[0:-1] != payload:
            raise Exception(
                'Unexpected payload : %r (expected) vs %r (actual)' %
                (payload, received[0:-1]))

    def send_close(self):
        _send_bytes(self._socket, self._CLOSE_FRAME)

    def assert_receive_close(self):
        closing = _receive_bytes(self._socket, len(self._CLOSE_FRAME))
        if closing != self._CLOSE_FRAME:
            raise Exception('Didn\'t receive closing handshake')


class ClientOptions(object):
    def __init__(self):
        self.server_host = ''
        self.origin = ''
        self.resource = ''
        self.server_port = -1
        self.socket_timeout = 1000
        self.use_tls = False


class Client(object):
    """WebSocket client."""

    def __init__(self, options, handshake, stream_class):
        self._logger = util.get_class_logger(self)

        self._options = options
        self._socket = None

        self._handshake = handshake
        self._stream_class = stream_class

    def connect(self):
        self._socket = socket.socket()
        self._socket.settimeout(self._options.socket_timeout)

        self._socket.connect((self._options.server_host,
                              self._options.server_port))
        if self._options.use_tls:
            self._socket = _TLSSocket(self._socket)

        self._handshake.handshake(self._socket)

        self._stream = self._stream_class(self._socket)

        self._logger.info('Connection established')

    def send_message(self, message, end=True):
        self._stream.send_text(message, end)

    def assert_receive(self, payload):
        self._stream.assert_receive_text(payload)

    def send_close(self):
        self._stream.send_close()

    def assert_receive_close(self):
        self._stream.assert_receive_close()

    def close_socket(self):
        self._socket.close()

    def assert_connection_closed(self):
        try:
            _ = _receive_bytes(self._socket, 1)
        except Exception, e:
            if str(e) != 'connection closed unexpectedly':
                raise
            return

        raise Exception('Connection is not closed')


def create_client(options):
    return Client(
        options, WebSocketHybi00Handshake(options, '1'), WebSocketStream)


def create_client_hybi00(options):
    return Client(
        options,
        WebSocketHybi00Handshake(options, '0'),
        WebSocketStreamHixie75)


def create_client_hixie75(options):
    return Client(
        options, WebSocketHixie75Handshake(options), WebSocketStreamHixie75)


# vi:sts=4 sw=4 et
