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


"""Web Socket extension for Apache HTTP Server.

mod_pywebsocket is a Web Socket extension for Apache HTTP Server
intended for testing or experimental purposes. mod_python is required.

Installation:

0. Prepare an Apache HTTP Server for which mod_python is enabled.

1. Specify the following Apache HTTP Server directives to suit your
   configuration.

   If mod_pywebsocket is not in the Python path, specify the following.
   <websock_lib> is the directory where mod_pywebsocket is installed.

       PythonPath "sys.path+['<websock_lib>']"

   Always specify the following. <websock_handlers> is the directory where
   user-written Web Socket handlers are placed.

       PythonOption mod_pywebsocket.handler_root <websock_handlers>
       PythonHeaderParserHandler mod_pywebsocket.headerparserhandler

   Example snippet of httpd.conf:
   (mod_pywebsocket is in /websock_lib, Web Socket handlers are in
   /websock_handlers, port is 80 for ws, 443 for wss.)

       <IfModule python_module>
         PythonPath "sys.path+['/websock_lib']"
         PythonOption mod_pywebsocket.handler_root /websock_handlers
         PythonHeaderParserHandler mod_pywebsocket.headerparserhandler
       </IfModule>

Writing Web Socket handlers:

When a Web Socket request comes in, the resource name
specified in the handshake is considered as if it is a file path under
<websock_handlers> and the handler defined in
<websock_handlers>/<resource_name>_wsh.py is invoked.

For example, if the resource name is /example/chat, the handler defined in
<websock_handlers>/example/chat_wsh.py is invoked.

A Web Socket handler is composed of the following two functions:

    web_socket_shake_hands(request)
    web_socket_transfer_data(request)

where:
    request: mod_python request.

web_socket_shake_hands is called during the handshake after the headers
are successfully parsed and Web Socket properties (ws_location,
ws_origin, ws_protocol, and ws_resource) are added to request.
A handler can reject the request by raising an exception.

web_socket_transfer_data is called after the handshake completed
successfully. A handler can receive/send messages from/to the client
using request. mod_pywebsocket.msgutil module provides utilities
for data transfer.
"""


# vi:sts=4 sw=4 et tw=72
