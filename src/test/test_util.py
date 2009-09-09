#!/usr/bin/env python
#
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


"""Tests for util module."""


import unittest

import config  # This must be imported before mod_pywebsocket.
from mod_pywebsocket import util


class UtilTest(unittest.TestCase):
    def test_get_stack_trace(self):
        self.assertEqual('None\n', util.get_stack_trace())
        try:
            a = 1 / 0  # Intentionally raise exception
        except Exception:
            trace = util.get_stack_trace()
            self.failUnless(trace.startswith('Traceback'))
            self.failUnless(trace.find('ZeroDivisionError') != -1)

    def test_parse_port_list(self):
        ports, warnings = util.parse_port_list('10')
        self.assertEqual(1, len(ports))
        self.assertEqual(10, ports[0])
        self.assertEqual(0, len(warnings))

        ports, warnings = util.parse_port_list('100, 200 , 300, ,,')
        self.assertEqual(3, len(ports))
        for expected, actual in zip([100, 200, 300], ports):
            self.assertEqual(expected, actual)
        self.assertEqual(0, len(warnings))

        ports, warnings = util.parse_port_list('0x100,200')
        self.assertEqual(1, len(ports))
        self.assertEqual(200, ports[0])
        self.assertEqual(1, len(warnings))


if __name__ == '__main__':
    unittest.main()


# vi:sts=4 sw=4 et
