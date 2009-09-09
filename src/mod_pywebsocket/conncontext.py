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


"""Web Socket connection context.
"""


class ConnContext(object):
    """Web Socket connection context.

    This class has properties related to a Web Socket connection to be
    referenced by handlers.
    """

    def __init__(self, conn, resource=None, protocol=None, origin=None,
                 secure=False, location=None, headers=None):
        """Construct an instance.

        Args:
            conn: mod_python.apache.mp_conn object.
            resource: Web Socket resource name specified in the handshake.
            protocol: Web Socket protocol specified in the handshake. None
                      if not specified.
            origin: Web Socket origin.
            secure: Whether the connection is secure (wss).
            location: Web Socket location.
            headers: Dictionary of headers sent from the client.
        """

        self.conn = conn
        self.resource = resource
        self.protocol = protocol
        self.origin = origin
        self.secure = secure
        self.location = location
        if headers:
            self.headers = headers
        else:
            self.headers = {}


# vi:sts=4 sw=4 et
