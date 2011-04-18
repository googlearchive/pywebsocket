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


"""Simple WebSocket client named echo_client just because of historical reason.

mod_pywebsocket directory must be in PYTHONPATH.

Example Usage:

# server setup
 % cd $pywebsocket
 % PYTHONPATH=$cwd/src python ./mod_pywebsocket/standalone.py -p 8880 \
    -d $cwd/src/example

# run client
 % PYTHONPATH=$cwd/src python ./src/example/echo_client.py -p 8880 \
     -s localhost \
     -o http://localhost -r /echo -m test

or

# run echo client to test IETF HyBi 00 protocol
 run with --protocol-version=hybi00

or

# server setup to test Hixie 75 protocol
 run with --allow-draft75

# run echo client to test Hixie 75 protocol
 run with --protocol-version=hixie75
"""


import codecs
import logging
from optparse import OptionParser
import random
import re
import socket
import struct
import sys

from mod_pywebsocket import common
from mod_pywebsocket.stream import Stream
from mod_pywebsocket.stream import StreamHixie75
from mod_pywebsocket import util


_TIMEOUT_SEC = 10
_UNDEFINED_PORT = -1

_UPGRADE_HEADER = 'Upgrade: WebSocket\r\n'
_CONNECTION_HEADER = 'Connection: Upgrade\r\n'

# Special message that tells the echo server to start closing handshake
_GOODBYE_MESSAGE = 'Goodbye'


def _build_method_line(resource):
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
    if ((not secure and port != common.DEFAULT_WEB_SOCKET_PORT) or
        (secure and port != common.DEFAULT_WEB_SOCKET_SECURE_PORT)):
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


class ClientHandshakeProcessorHybi00(object):
    """WebSocket opening handshake processor for
    draft-ietf-hybi-thewebsocketprotocol-00 (equivalent to
    draft-hixie-thewebsocketprotocol-76).
    """

    def __init__(self, socket, options):
        self._socket = socket
        self._options = options

    def handshake(self):
        """Performs opening handshake on the specified socket.

        Raises:
            Exception: handshake failed.
        """
        # 4.1 5. send request line.
        self._socket.sendall(_build_method_line(self._options.resource))
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

        if self._options.protocol_version == 'hybi01':
            fields.append('Sec-WebSocket-Draft: 1\r\n')
        elif self._options.protocol_version == 'hybi00':
            fields.append('Sec-WebSocket-Draft: 0\r\n')
        else:
            raise Exception('illegal --protocol-version flag: %s' %
                            self._options.protocol_version)

        # 4.1 24. For each string in /fields/, in a random order: send the
        # string, encoded as UTF-8, followed by a UTF-8 encoded U+000D CARRIAGE
        # RETURN U+000A LINE FEED character pair (CRLF).
        random.shuffle(fields)
        for field in fields:
            self._socket.sendall(field)
        # 4.1 25. send a UTF-8-encoded U+000D CARRIAGE RETURN U+000A LINE FEED
        # character pair (CRLF).
        self._socket.sendall('\r\n')
        # 4.1 26. let /key3/ be a string consisting of eight random bytes (or
        # equivalently, a random 64 bit integer encoded in a big-endian order).
        self._key3 = self._generate_key3()
        # 4.1 27. send /key3/ to the server.
        self._socket.sendall(self._key3)
        logging.debug('key3     : %s' % util.hexify(self._key3))

        logging.info('Sent handshake')

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
            raise Exception('not one upgrade: %s' % fields['upgrade'])
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

        logging.debug('num+key3 : %d, %d, %s' % (
            self._number1, self._number2,
            util.hexify(self._key3)))
        logging.debug('challenge: %s' % util.hexify(challenge))

        # 4.1 43. let /expected/ be the MD5 fingerprint of /challenge/ as a
        # big-endian 128 bit string.
        expected = util.md5_hash(challenge).digest()
        logging.debug('expected : %s' % util.hexify(expected))

        # 4.1 44. read sixteen bytes from the server.
        # let /reply/ be those bytes.
        reply = _receive_bytes(self._socket, 16)
        logging.debug('reply    : %s' % util.hexify(reply))

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


class ClientHandshakeProcessorHixie75(object):
    """WebSocket opening handshake processor for
    draft-hixie-thewebsocketprotocol-75.
    """

    _EXPECTED_RESPONSE = (
        'HTTP/1.1 101 Web Socket Protocol Handshake\r\n' +
        _UPGRADE_HEADER +
        _CONNECTION_HEADER)

    def __init__(self, socket, options):
        self._socket = socket
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

    def handshake(self):
        """Performs opening handshake on the specified socket.

        Raises:
            Exception: handshake failed.
        """

        self._socket.sendall(_build_method_line(self._options.resource))
        self._socket.sendall(_UPGRADE_HEADER)
        self._socket.sendall(_CONNECTION_HEADER)
        self._socket.sendall(_format_host_header(
            self._options.server_host,
            self._options.server_port,
            self._options.use_tls))
        self._socket.sendall(_origin_header(self._options.origin))
        self._socket.sendall('\r\n')

        logging.info('Sent handshake')

        for expected_char in ClientHandshakeProcessorHixie75._EXPECTED_RESPONSE:
            received = _receive_bytes(self._socket, 1)
            if expected_char != received:
                raise Exception('Handshake failure')
        # We cut corners and skip other headers.
        self._skip_headers()


class ClientConnection(object):
    """A wrapper for socket object to provide the mp_conn interface.
    mod_pywebsocket library is designed to be working on Apache mod_python's
    mp_conn object.
    """

    def __init__(self, socket):
        self._socket = socket

    def write(self, data):
        self._socket.sendall(data)

    def read(self, n):
        return self._socket.recv(n)


class ClientRequest(object):
    def __init__(self, socket):
        self.connection = ClientConnection(socket)


class EchoClient(object):
    """WebSocket echo client."""

    def __init__(self, options, handshake_class, stream_class):
        self._options = options
        self._socket = None
        self._handshake_class = handshake_class
        self._stream_class = stream_class

    def run(self):
        """Run the client.

        Shake hands and then repeat sending message and receiving its echo.
        """

        self._socket = socket.socket()
        self._socket.settimeout(self._options.socket_timeout)
        try:
            self._socket.connect((self._options.server_host,
                                  self._options.server_port))
            if self._options.use_tls:
                self._socket = _TLSSocket(self._socket)

            self._handshake = self._handshake_class(
                self._socket, self._options)
            self._handshake.handshake()

            logging.info('Connection established')

            request = ClientRequest(self._socket)
            self._stream = self._stream_class(request)
            if self._options.protocol_version == 'hybi01':
                request.ws_version = common.VERSION_HYBI01
            elif self._options.protocol_version == 'hybi00':
                request.ws_version = common.VERSION_HYBI00
            elif self._options.protocol_version == 'hixie75':
                request.ws_version = common.VERSION_HIXIE75
            else:
                raise Exception('illegal --protocol-version flag: %s' %
                                self._options.protocol_version)

            for line in self._options.message.split(','):
                self._stream.send_message(line)
                if self._options.verbose:
                    print 'Send: %s' % line
                try:
                    received = self._stream.receive_message()

                    if self._options.verbose:
                        print 'Recv: %s' % received
                except Exception, e:
                    if self._options.verbose:
                        print 'Error: %s' % e
                    raise

            if request.ws_version != common.VERSION_HIXIE75:
                self._do_closing_handshake()
        finally:
            self._socket.close()

    def _do_closing_handshake(self):
        """Perform closing handshake using the specified closing frame."""

        if self._options.message.split(',')[-1] == _GOODBYE_MESSAGE:
            # requested server initiated closing handshake, so
            # expecting closing handshake message from server.
            logging.info('Wait for server-initiated closing handshake')
            message = self._stream.receive_message()
            if message is None:
                print 'Recv close'
                print 'Send ack'
                logging.info(
                    'Received closing handshake and sent ack')
                return
        print 'Send close'
        self._stream.close_connection()
        logging.info('Sent closing handshake')
        print 'Recv ack'
        logging.info('Received ack')


def main():
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout)

    parser = OptionParser()
    parser.add_option('-s', '--server-host', '--server_host',
                      dest='server_host', type='string',
                      default='localhost', help='server host')
    parser.add_option('-p', '--server-port', '--server_port',
                      dest='server_port', type='int',
                      default=_UNDEFINED_PORT, help='server port')
    parser.add_option('-o', '--origin', dest='origin', type='string',
                      default='http://localhost/', help='origin')
    parser.add_option('-r', '--resource', dest='resource', type='string',
                      default='/echo', help='resource path')
    parser.add_option('-m', '--message', dest='message', type='string',
                      help=('comma-separated messages to send. '
                           '%s will force close the connection from server.' %
                            _GOODBYE_MESSAGE))
    parser.add_option('-q', '--quiet', dest='verbose', action='store_false',
                      default=True, help='suppress messages')
    parser.add_option('-t', '--tls', dest='use_tls', action='store_true',
                      default=False, help='use TLS (wss://)')
    parser.add_option('-k', '--socket-timeout', '--socket_timeout',
                      dest='socket_timeout', type='int', default=_TIMEOUT_SEC,
                      help='Timeout(sec) for sockets')
    parser.add_option('--draft75', dest='draft75',
                       action='store_true', default=False,
                      help='use the Hixie 75 protocol. This overrides '
                      'protocol-version flag')
    parser.add_option('--protocol-version', '--protocol_version',
                      dest='protocol_version',
                      type='string', default='hybi01',
                      help='WebSocket protocol version to use. One of '
                      + '\'hybi01\', \'hybi00\', \'hixie75\'')
    parser.add_option('--log-level', '--log_level', type='choice',
                      dest='log_level', default='warn',
                      choices=['debug', 'info', 'warn', 'error', 'critical'],
                      help='Log level.')

    (options, unused_args) = parser.parse_args()

    logger = logging.getLogger()
    logger.setLevel(logging.getLevelName(options.log_level.upper()))

    if options.draft75:
        options.protocol_version = 'hixie75'

    # Default port number depends on whether TLS is used.
    if options.server_port == _UNDEFINED_PORT:
        if options.use_tls:
            options.server_port = common.DEFAULT_WEB_SOCKET_SECURE_PORT
        else:
            options.server_port = common.DEFAULT_WEB_SOCKET_PORT

    # optparse doesn't seem to handle non-ascii default values.
    # Set default message here.
    if not options.message:
        options.message = u'Hello,\u65e5\u672c'   # "Japan" in Japanese

    if options.protocol_version == 'hybi01':
        EchoClient(
            options, ClientHandshakeProcessorHybi00, Stream).run()
    elif options.protocol_version == 'hybi00':
        EchoClient(
            options, ClientHandshakeProcessorHybi00, StreamHixie75).run()
    elif options.protocol_version == 'hixie75':
        EchoClient(
            options, ClientHandshakeProcessorHixie75, StreamHixie75).run()
    else:
        raise Exception(
            'Invalid protocol version flag: %s' % options.protocol_version)


if __name__ == '__main__':
    main()


# vi:sts=4 sw=4 et
