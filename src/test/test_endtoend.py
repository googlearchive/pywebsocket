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

"""Test for end-to-end."""

import client_for_testing
import config  # to fix sys.path.
import logging
import os
import signal
import socket
import subprocess
import sys
import time
import unittest


# Special message that tells the echo server to start closing handshake
_GOODBYE_MESSAGE = 'Goodbye'


# Test body functions
def _echo_check_procedure(client):
    client.connect()

    client.send_message('test')
    client.assert_receive('test')

    client.send_close()
    client.assert_receive_close()

    client.assert_connection_closed()


def _echo_check_procedure_with_goodbye(client):
    client.connect()

    client.send_message('test')
    client.assert_receive('test')

    client.send_message(_GOODBYE_MESSAGE)
    client.assert_receive(_GOODBYE_MESSAGE)

    client.assert_receive_close()
    client.send_close()

    client.assert_connection_closed()


class EndToEndTest(unittest.TestCase):
    def setUp(self):
        self.top_dir = os.path.join(os.path.split(__file__)[0], '..')
        os.putenv('PYTHONPATH', os.path.pathsep.join(sys.path))
        self.standalone_command = os.path.join(
            self.top_dir, 'mod_pywebsocket', 'standalone.py')
        self.document_root = os.path.join(self.top_dir, 'example')
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        (_, self.test_port) = s.getsockname()
        s.close()

        self._options = client_for_testing.ClientOptions()
        self._options.server_host = 'localhost'
        self._options.origin = 'http://localhost'
        self._options.resource = '/echo'
        self._options.server_port = self.test_port

    def _run_python_command(self, commandline):
        return subprocess.Popen([sys.executable] + commandline, close_fds=True)

    def _run_server(self, allow_draft75=False):
        args = [self.standalone_command,
                '-p', str(self.test_port),
                '-d', self.document_root]

        # Inherit the level set to the root logger by test runner.
        root_logger = logging.getLogger()
        log_level = root_logger.getEffectiveLevel()
        if log_level != logging.NOTSET:
            args.append('--log-level')
            args.append(logging.getLevelName(log_level).lower())

        if allow_draft75:
            args.append('--allow-draft75')

        return self._run_python_command(args)

    def _kill_process(self, pid):
        if sys.platform in ('win32', 'cygwin'):
            subprocess.call(
                ('taskkill.exe', '/f', '/pid', str(pid)), close_fds=True)
        else:
            os.kill(pid, signal.SIGKILL)

    def _run_hybi01_test(self, test_function):
        server = self._run_server()
        try:
            # TODO(tyoshino): add some logic to poll the server until it becomes
            # ready
            time.sleep(0.2)

            client = client_for_testing.create_client(self._options)
            try:
                test_function(client)
            finally:
                client.close_socket()
        finally:
            self._kill_process(server.pid)

    def test_echo(self):
        self._run_hybi01_test(_echo_check_procedure)

    def test_echo_server_close(self):
        self._run_hybi01_test(_echo_check_procedure_with_goodbye)

    def _run_hybi00_test(self, test_function):
        server = self._run_server()
        try:
            time.sleep(0.2)

            client = client_for_testing.create_client_hybi00(self._options)
            try:
                test_function(client)
            finally:
                client.close_socket()
        finally:
            self._kill_process(server.pid)

    def test_echo_hybi00(self):
        self._run_hybi00_test(_echo_check_procedure)

    def test_echo_server_close_hybi00(self):
        self._run_hybi00_test(_echo_check_procedure_with_goodbye)

    def _run_hixie75_test(self, test_function):
        server = self._run_server(allow_draft75=True)
        try:
            time.sleep(0.2)

            client = client_for_testing.create_client_hixie75(self._options)
            try:
                test_function(client)
            finally:
                client.close_socket()
        finally:
            self._kill_process(server.pid)

    def test_echo_hixie75(self):
        def test_function(client):
            client.connect()

            client.send_message('test')
            client.assert_receive('test')

        self._run_hixie75_test(test_function)

    def test_echo_server_close_hixie75(self):
        def test_function(client):
            client.connect()

            client.send_message('test')
            client.assert_receive('test')

            client.send_message(_GOODBYE_MESSAGE)
            client.assert_receive(_GOODBYE_MESSAGE)

        self._run_hixie75_test(test_function)


if __name__ == '__main__':
    unittest.main()


# vi:sts=4 sw=4 et
