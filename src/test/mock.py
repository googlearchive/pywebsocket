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


"""Mocks for testing.
"""


import Queue
import threading


class _MockConnBase(object):
    """Base class of mocks for mod_python.apache.mp_conn.

    This enables tests to check what is written to a (mock) mp_conn.
    """

    def __init__(self):
        self._write_data = []

    def write(self, data):
        """Override mod_python.apache.mp_conn.write."""

        self._write_data.append(data)

    def written_data(self):
        """Get bytes written to this mock."""

        return ''.join(self._write_data)


class MockConn(_MockConnBase):
    """Mock for mod_python.apache.mp_conn.

    This enables tests to specify what should be read from a (mock) mp_conn as
    well as to check what is written to it.
    """

    def __init__(self, read_data):
        """Constructs an instance.

        Args:
            read_data: bytes that should be returned when read* methods are
            called.
        """

        _MockConnBase.__init__(self)
        self._read_data = read_data
        self._read_pos = 0

    def readline(self):
        """Override mod_python.apache.mp_conn.readline."""

        if self._read_pos >= len(self._read_data):
            return ''
        end_index = self._read_data.find('\n', self._read_pos) + 1
        if end_index == 0:
            end_index = len(self._read_data)
        return self._read_up_to(end_index)

    def read(self, length):
        """Override mod_python.apache.mp_conn.read."""

        if self._read_pos >= len(self._read_data):
            return ''
        end_index = min(len(self._read_data), self._read_pos + length)
        return self._read_up_to(end_index)

    def _read_up_to(self, end_index):
        line = self._read_data[self._read_pos:end_index]
        self._read_pos = end_index
        return line


class MockBlockingConn(_MockConnBase):
    """Blocking mock for mod_python.apache.mp_conn.

    This enables tests to specify what should be read from a (mock) mp_conn as
    well as to check what is written to it.
    Callers of read* methods will block if there is no bytes available.
    """

    def __init__(self):
        _MockConnBase.__init__(self)
        self._queue = Queue.Queue()

    def readline(self):
        """Override mod_python.apache.mp_conn.readline."""
        line = ''
        while True:
            ch = self._queue.get()
            line += ch
            if ch == '\n':
                return line

    def read(self, length):
        """Override mod_python.apache.mp_conn.read."""

        data = ''
        for _ in range(length):
            data += self._queue.get()
        return data

    def put_bytes(self, bytes):
        """Put bytes to be read from this mock.

        Args:
            bytes: bytes to be read.
        """

        for byte in bytes:
            self._queue.put(byte)


class MockDispatcher(object):
    """Mock for dispatch.Dispatcher."""

    def shake_hands(self, conn_context):
        pass

    def transfer_data(self, conn_context):
        pass


# vi:sts=4 sw=4 et
