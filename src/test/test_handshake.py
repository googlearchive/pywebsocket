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


"""Tests for handshake module."""


import unittest

import set_sys_path  # Update sys.path to locate mod_pywebsocket module.

from mod_pywebsocket.handshake._base import HandshakeError
from mod_pywebsocket.handshake._base import validate_subprotocol


class HandshakerTest(unittest.TestCase):
    """A unittest for handshake module."""

    def test_validate_subprotocol(self):
        validate_subprotocol('sample')  # should succeed.
        validate_subprotocol('Sample')  # should succeed.
        validate_subprotocol('sample\x20protocol')  # should succeed.
        validate_subprotocol('sample\x7eprotocol')  # should succeed.
        self.assertRaises(HandshakeError,
                          validate_subprotocol,
                          '')
        self.assertRaises(HandshakeError,
                          validate_subprotocol,
                          'sample\x19protocol')
        self.assertRaises(HandshakeError,
                          validate_subprotocol,
                          'sample\x7fprotocol')
        self.assertRaises(HandshakeError,
                          validate_subprotocol,
                          # "Japan" in Japanese
                          u'\u65e5\u672c')
if __name__ == '__main__':
    unittest.main()


# vi:sts=4 sw=4 et
