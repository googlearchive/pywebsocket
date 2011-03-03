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


"""Tests for _stream_hybi04 module."""


import unittest

import set_sys_path  # Update sys.path to locate mod_pywebsocket module.

from mod_pywebsocket.util import RepeatedXorMasker


class RepeatedXorMaskerTest(unittest.TestCase):
    def test_mask(self):
        # Sample input e6,97,a5 is U+65e5 in UTF-8
        masker = RepeatedXorMasker('\xff\xff\xff')
        result = masker.mask('\xe6\x97\xa5')
        self.assertEqual('\x19\x68\x5a', result)

        masker = RepeatedXorMasker('\x00\x00\x00')
        result = masker.mask('\xe6\x97\xa5')
        self.assertEqual('\xe6\x97\xa5', result)

        masker = RepeatedXorMasker('\xe6\x97\xa5')
        result = masker.mask('\xe6\x97\xa5')
        self.assertEqual('\x00\x00\x00', result)

    def test_mask_twice(self):
        masker = RepeatedXorMasker('\x00\x7f\xff')
        # mask[0], mask[1], ... will be used.
        result = masker.mask('\x00\x00\x00\x00\x00')
        self.assertEqual('\x00\x7f\xff\x00\x7f', result)
        # mask[2], mask[0], ... will be used for the next call.
        result = masker.mask('\x00\x00\x00\x00\x00')
        self.assertEqual('\xff\x00\x7f\xff\x00', result)


if __name__ == '__main__':
    unittest.main()


# vi:sts=4 sw=4 et
