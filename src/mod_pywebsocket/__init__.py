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
   <install_dir> is the directory where mod_pywebsocket is installed.

       PythonPath "sys.path+['<install_dir>']"

   Always specify the following. <handler_root> is the directory where
   user-written Web Socket handlers are placed.

       PythonOption mod_pywebsocket.handler_root <handler_root>
       PythonConnectionHandler mod_pywebsocket.connhandler

   Example snippet of httpd.conf:
   (mod_pywebsocket is in /websock_lib, Web Socket handlers are in
   /websock_handlers, port is 80 for ws, 443 for wss.)

       <IfModule python_module>

         PythonPath "sys.path+['/websock_lib']"
         PythonOption mod_pywebsocket.handler_root /websock_handlers
         PythonOption mod_pywebsocket.secure_ports 443

         Listen 80
         <VirtualHost _default_:80>
           PythonConnectionHandler mod_pywebsocket.connhandler
           LogLevel debug
         </VirtualHost>

         Listen 443
         <VirtualHost _default_:443>
           PythonConnectionHandler mod_pywebsocket.connhandler
           LogLevel debug
           SSLEngine on
           # ... Other SSL configuration here ...
         </VirtualHost>

       </IfModule>

    Note:
    The above httpd.conf won't work if port 80 and 443 are already used
    for other purposes, e.g., for HTTP and HTTPS. Use different ports in
    such cases.

Writing Web Socket handlers:

When a Web Socket connection request comes in, the resource name
specified in the handshake is considered as if it is a file path under
<handler_root> and the handler defined in
<handler_root>/<resource_name>_wsh.py is invoked.

For example, if the resource name is /example/chat, the handler defined in
<handler_root>/example/chat_wsh.py is invoked.

A Web Socket handler is composed of the following two functions:

    web_socket_shake_hands(conn_context)
    web_socket_transfer_data(conn_context)

where:
    conn_context: Connection context (conncontext.ConnContext).

web_socket_shake_hands is called during the handshake after the headers
are successfully parsed and conn_connection properties (protocol,
origin, etc.) are set. A handler can reject the connection by raising an
exception.

web_socket_transfer_data is called after the handshake completed
successfully. A handler can receive/send messages from/to the client
using conn_context. mod_pywebsocket.msgutil module provides utilities
for data transfer.
"""


# vi:sts=4 sw=4 et tw=72
