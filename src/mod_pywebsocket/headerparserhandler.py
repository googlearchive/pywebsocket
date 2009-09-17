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


"""PythonHeaderParserHandler for mod_pywebsocket.

Apache HTTP Server and mod_python must be configured such that this
function is called to handle Web Socket request.
"""


from mod_python import apache

import dispatch
import handshake
import util


# PythonOption to specify the handler root directory.
_PYOPT_HANDLER_ROOT = 'mod_pywebsocket.handler_root'


def _create_dispatcher():
    _HANDLER_ROOT = apache.main_server.get_options().get(
            _PYOPT_HANDLER_ROOT, None)
    if not _HANDLER_ROOT:
        raise Exception('PythonOption %s is not defined' % _PYOPT_HANDLER_ROOT,
                        apache.APLOG_ERR)
    dispatcher = dispatch.Dispatcher(_HANDLER_ROOT)
    for warning in dispatcher.source_warnings():
        apache.log_error('mod_pywebsocket: %s' % warning, apache.APLOG_WARNING)
    return dispatcher


# Initialize
_dispatcher = _create_dispatcher()


def headerparserhandler(request):
    """Handle request.

    Args:
        request: mod_python request.

    This function is named headerparserhandler because it is the default name
    for a PythonHeaderParserHandler.
    """

    try:
        handshaker = handshake.Handshaker(request, _dispatcher)
        handshaker.shake_hands()
        request.log_error('mod_pywebsocket: resource:%r' % request.ws_resource,
                          apache.APLOG_DEBUG)
        _dispatcher.transfer_data(request)
    except handshake.HandshakeError, e:
        # Handshake for ws/wss failed.
        # But the request can be valid http/https request.
        request.log_error('mod_pywebsocket: %s' % e, apache.APLOG_INFO)
        return apache.DECLINED
    except dispatch.DispatchError, e:
        request.log_error('mod_pywebsocket: %s' % e, apache.APLOG_WARNING)
        return apache.DECLINED
    return apache.DONE  # Return DONE such that no other handlers are invoked.


# vi:sts=4 sw=4 et
