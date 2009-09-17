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


"""Web Sockets utilities.
"""


import StringIO
import traceback


def get_stack_trace():
    """Get the current stack trace as string.

    This is needed to support Python 2.3.
    TODO: Remove this when we only support Python 2.4 and above.
          Use traceback.format_exc instead.
    """

    out = StringIO.StringIO()
    traceback.print_exc(file=out)
    return out.getvalue()


# vi:sts=4 sw=4 et
