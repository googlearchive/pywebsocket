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


def web_socket_shake_hands(request):
    return True


def web_socket_transfer_data(request):
    request.connection.write('sub/e_wsh.py is called for %s, %s' %
                             (request.ws_resource, request.ws_protocol))


# vi:sts=4 sw=4 et
