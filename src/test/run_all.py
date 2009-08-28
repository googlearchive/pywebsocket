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


"""Run all tests in the same directory.
"""


import os
import re
import unittest


_TEST_MODULE_PATTERN = re.compile(r'^(test_.+)\.py$')


def _list_test_modules(directory):
    module_names = []
    for filename in os.listdir(directory):
        match = _TEST_MODULE_PATTERN.search(filename)
        if match:
            module_names.append(match.group(1))
    return module_names


def _suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromNames(
            _list_test_modules(os.path.join(os.path.split(__file__)[0], '.')))


if __name__ == '__main__':
    unittest.main(defaultTest='_suite')


# vi:sts=4 sw=4 et
