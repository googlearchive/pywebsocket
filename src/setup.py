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


"""Set up script for mod_pywebsocket.
"""


from distutils.core import setup
import sys


_PACKAGE_NAME = 'mod_pywebsocket'

if sys.version < '2.3':
    print >>sys.stderr, '%s requires Python 2.3 or later.' % _PACKAGE_NAME
    sys.exit(1)

setup(author='Yuzo Fujishima',
      author_email='yuzo@chromium.org',
      description='Web Socket extension for Apache HTTP Server.',
      long_description=(
              'mod_pywebsocket is an Apache HTTP Server extension for '
              'Web Socket (http://tools.ietf.org/html/'
              'draft-hixie-thewebsocketprotocol). '
              'See mod_pywebsocket/__init__.py for more detail.'),
      license='http://www.apache.org/licenses/LICENSE-2.0',
      name=_PACKAGE_NAME,
      packages=[_PACKAGE_NAME],
      url='http://code.google.com/p/pywebsocket/',
      version='0.1.0',
      )


# vi:sts=4 sw=4 et
