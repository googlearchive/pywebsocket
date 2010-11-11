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


"""Stream of WebSocket protocol.
"""

from mod_pywebsocket import msgutil

class ConnectionTerminatedException(msgutil.ConnectionTerminatedException):
  pass


class Stream(object):
  """Stream of WebSocket messages.

  This class provides abstract interface to access WebSocket stream of frames.
  TODO(ukai): dispatch framing based on Sec-WebSocket-Draft.
  """

  def __init__(self, request):
    """Construct an instance.

    Args:
      request: mod_python request.
    """
    self._request = request
    self._request.client_terminated = False
    self._request.server_terminated = False


  def send_message(self, message):
    """Send message.

    Args:
      message: unicode string to send.
    """
    if self._request.server_terminated:
      raise ConnectionTerminatedException
    msgutil._write(self._request, '\x00' + message.encode('utf-8') + '\xff')

  def receive_message(self):
    """Receive a WebSocket frame and return its payload an unicode string.

    Returns:
      payload unicode string in a WebSocket frame.
    """
    if self._request.client_terminated:
      raise ConnectionTerminatedException
    while True:
        # Read 1 byte.
        # mp_conn.read will block if no bytes are available.
        # Timeout is controlled by TimeOut directive of Apache.
        frame_type_str = msgutil._read(self._request, 1)
        frame_type = ord(frame_type_str[0])
        if (frame_type & 0x80) == 0x80:
            # The payload length is specified in the frame.
            # Read and discard.
            length = msgutil._payload_length(self._request)
            msgutil._receive_bytes(self._request, length)
            # 5.3 3. 12. if /type/ is 0xFF and /length/ is 0, then set the
            # /client terminated/ flag and abort these steps.
            if frame_type == 0xFF and length == 0:
                self._request.client_terminated = True
                raise ConnectionTerminatedException
        else:
            # The payload is delimited with \xff.
            bytes = msgutil._read_until(self._request, '\xff')
            # The Web Socket protocol section 4.4 specifies that invalid
            # characters must be replaced with U+fffd REPLACEMENT CHARACTER.
            message = bytes.decode('utf-8', 'replace')
            if frame_type == 0x00:
                return message
            # Discard data of other types.

  def close_connection(self):
    """Closes a WebSocket connection."""
    if self._request.server_terminated:
      return
    # 5.3 the server may decide to terminate the WebSocket connection by
    # running through the following steps:
    # 1. send a 0xFF byte and a 0x00 byte to the client to indicate the start
    # of the closing handshake.
    msgutil._write(self._request, '\xff\x00')
    self._request.server_terminated = True
    # TODO(ukai): 2. wait until the /client terminated/ flag has been set, or
    # until a server-defined timeout expires.
    # TODO: 3. close the WebSocket connection.
    # note: mod_python Connection (mp_conn) doesn't have close method.
