
# pywebsocket #

## What is it? ##

The pywebsocket project aims to provide a [WebSocket](http://tools.ietf.org/html/rfc6455) standalone server and a WebSocket extension for [Apache HTTP Server](http://httpd.apache.org/), mod\_pywebsocket.

pywebsocket is intended for **testing** or **experimental** purposes. To run with Apache HTTP Server, [mod\_python](http://www.modpython.org/) is required. For wss, mod\_ssl is also required.

pywebsocket supports RFC 6455 (and [some legacy protocols](WebSocketProtocolSpec.md)) and the following extension.

  * [WebSocket Per-message Compression (permessage-deflate)](http://tools.ietf.org/html/draft-ietf-hybi-permessage-compression-17)

## How can I use it? ##

To try mod\_pywebsocket, please do:
```
svn checkout http://pywebsocket.googlecode.com/svn/trunk/ pywebsocket-read-only
```
and follow the instructions in [pywebsocket-read-only/src/README](http://code.google.com/p/pywebsocket/source/browse/trunk/src/README).

To run mod\_pywebsocket as an Apache HTTP Server extension module, please read comments in
[pywebsocket-read-only/mod\_pywebsocket/\_\_init\_\_.py](http://code.google.com/p/pywebsocket/source/browse/trunk/src/mod_pywebsocket/__init__.py).

To run mod\_pywebsocket as a standalone server (i.e., not using Apache HTTP Server), please
read comments in
[pywebsocket-read-only/mod\_pywebsocket/standalone.py](http://code.google.com/p/pywebsocket/source/browse/trunk/src/mod_pywebsocket/standalone.py).

See TestingYourWebSocketImplementation for quick tutorial for testing your WebSocket implementation using pywebsocket.

## Examples ##

The following is a list of **third party** examples.

  * http://code.google.com/p/websocket-sample/

## Questions or suggestions? ##

We have a list for users and developers. Please join http://groups.google.com/group/pywebsocket.

## For developers who intend to contribute to pywebsocket ##

### Legal ###

You must complete the [Individual Contributor License Agreement](http://code.google.com/legal/individual-cla-v1.0.html). You can do this online, and it only takes a minute. If you are contributing on behalf of a corporation, you must fill out the [Corporate Contributor License Agreement](http://code.google.com/legal/corporate-cla-v1.0.html) and send it to us as described on that page.

### Nuts and bolts ###

Basically, we apply PEP-8 coding style guide http://www.python.org/dev/peps/pep-0008/ to Python code in this project and in some case we follow some rules from Google Python style guide http://google-styleguide.googlecode.com/svn/trunk/pyguide.html if they don't conflict with PEP-8.

We use the shared Rietveld site hosted by Google AppEngine http://codereview.appspot.com for reviewing code. There's a list for watching review in Google Groups http://groups.google.com/group/pywebsocket-reviews and one for watching changes on bug tracker http://groups.google.com/group/pywebsocket-bugs.

See also WebSocketProtocolSpec, a note for developer about WebSocket protocol design