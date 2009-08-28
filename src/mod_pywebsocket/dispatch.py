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


"""Dispatch Web Socket connection request.
"""


import os
import re

import util


_SOURCE_PATH_PATTERN = re.compile(r'(?i)_wsh\.py$')
_SOURCE_SUFFIX = '_wsh.py'
_SHAKE_HANDS_HANDLER_NAME = 'web_socket_shake_hands'
_TRANSFER_DATA_HANDLER_NAME = 'web_socket_transfer_data'


class DispatchError(Exception):
    """Exception in dispatching Web Socket connection request."""

    pass


def _path_to_resource_converter(base_dir):
    base_dir = os.path.normpath(base_dir).replace('\\', '/')
    base_len = len(base_dir)
    suffix_len = len(_SOURCE_SUFFIX)
    def converter(path):
        if not path.endswith(_SOURCE_SUFFIX):
            return None
        path = os.path.normpath(path).replace('\\', '/')
        if not path.startswith(base_dir):
            return None
        return path[base_len:-suffix_len]
    return converter


def _source_file_paths(directory):
    """Yield Web Socket Handler source file names in the given directory."""

    for root, unused_dirs, files in os.walk(directory):
        for base in files:
            path = os.path.join(root, base)
            if _SOURCE_PATH_PATTERN.search(path):
                yield path


def _source(source_str):
    """Source a handler definition string."""

    global_dic = {}
    try:
        exec source_str in global_dic
    except Exception:
        raise DispatchError('Error in sourcing handler:' +
                            util.get_stack_trace())
    return (_extract_handler(global_dic, _SHAKE_HANDS_HANDLER_NAME),
            _extract_handler(global_dic, _TRANSFER_DATA_HANDLER_NAME))


def _extract_handler(dic, name):
    if name not in dic:
        raise DispatchError('%s is not defined.' % name)
    handler = dic[name]
    if not callable(handler):
        raise DispatchError('%s is not callable.' % name)
    return handler


class Dispatcher(object):
    """Dispatches Web Socket connection requests.

    This class maintains a map from resource name to handlers.
    """

    def __init__(self, root_dir):
        """Construct an instance.

        Args:
            root_dir: The directory where handler definition files are
            placed.
        """

        self._handlers = {}
        self._source_warnings = []
        self._source_files_in_dir(root_dir)

    def source_warnings(self):
        """Return warnings in sourcing handlers."""

        return self._source_warnings

    def shake_hands(self, conn_context):
        """Hook into Web Socket handshake.

        Select a handler based on conn_context.resource and call its
        web_socket_shake_hands function.

        Args:
            conn_context: Connection context.
        """

        shake_hands_, _ = self._handler(conn_context)
        try:
            shake_hands_(conn_context)
        except Exception:
            raise DispatchError('shake_hands() raised exception: ' +
                                util.get_stack_trace())

    def transfer_data(self, conn_context):
        """Let a handler transfer_data with a Web Socket client.

        Select a handler based on conn_context.resource and call its
        web_socket_transfer_data function.

        Args:
            conn_context: Connection context.
        """

        _, transfer_data_ = self._handler(conn_context)
        try:
            transfer_data_(conn_context)
        except Exception:
            raise DispatchError('transfer_data() raised exception: ' +
                                util.get_stack_trace())

    def _handler(self, conn_context):
        try:
            return self._handlers[conn_context.resource]
        except KeyError:
            raise DispatchError('No handler for: %r' % conn_context.resource)

    def _source_files_in_dir(self, root_dir):
        """Source all the handler source files in the directory."""

        to_resource = _path_to_resource_converter(root_dir)
        for path in _source_file_paths(root_dir):
            try:
                handler = _source(open(path).read())
            except DispatchError, e:
                self._source_warnings.append('%s: %s' % (path, e))
                continue
            self._handlers[to_resource(path)] = handler


# vi:sts=4 sw=4 et
