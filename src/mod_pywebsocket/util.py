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


def parse_port_list(port_list):
    """Parse comma-delimited list of port numbers.

    Args:
        port_list: Comma-delimited list of port numbers (str).
    Returns:
        (ports, warnings) where ports is a sequence of port numbers (int) and
        warnings is a sequence of warnings (str).

    Parse comma-delimited list of port numbers and return (ports, warnings)
    tuple. Whitespace and empty strings are ignored.
    """

    ports = []
    warnings = []
    for port in port_list.split(','):
        port = port.strip()
        if not port:
            continue
        try:
            ports.append(int(port))
        except ValueError, e:
            warnings.append(str(e))
    return ports, warnings


# vi:sts=4 sw=4 et
