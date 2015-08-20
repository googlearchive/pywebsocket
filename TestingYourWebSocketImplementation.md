# Testing your server implementation using echo\_client.py in pywebsocket #

For example, to connect to ws://example.com:12345/test using HyBi 13 version protocol, and send three text frames "Hello", "foo", "bar" to it, run this:

```
svn checkout http://pywebsocket.googlecode.com/svn/trunk/ pywebsocket-read-only
cd pywebsocket-read-only/src
PYTHONPATH=. python example/echo_client.py -s example.com -p 12345 -r /test \
  -m Hello,foo,bar --protocol_version=hybi13 --origin=http://example.com:12345/ \
  --log-level=debug
```

# Testing your client implementation using standalone.py in pywebsocket #

To launch pywebsocket standalone server on port 12345 with echo back service on /echo with HyBi 13, HyBi 08, HyBi 00 and Hixie 75 protocol support, run this:

```
svn checkout http://pywebsocket.googlecode.com/svn/trunk/ pywebsocket-read-only
cd pywebsocket-read-only/src
PYTHONPATH=. python mod_pywebsocket/standalone.py -p 12345 --allow-draft75 -d example --log-level debug
```

Open http://localhost:12345/console.html using your client and check if the messages you send are echoed back.

# Generating Sec-WebSocket-Accept manually #

Use this python code

```
import base64
import hashlib
def accept(v):
  s = hashlib.sha1()
  s.update(v + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11')
  return base64.b64encode(s.digest())
```

# Unmasking frame manually #

Use this python code

```
import binascii
def conv(s):
  return map(lambda x: ord(binascii.a2b_hex(x)), s.split(' '))
m = conv('fd 4b 40 b8')
d = conv('fe a1 15 d6 98 33 30 dd 9e 3f 25 dc dd 28 2f d6 89 22 2e cd 9c 3f 29 d7 93')
r = []
for i in xrange(len(d)):
  r.append(d[i] ^ m[i % 4])
print ' '.join(map(hex, r))
print ''.join(map(chr, r))
```

# TLS #

You can find files for testing at test/cert/

  * cacert.pem self-signed
  * cert.pem signed by cacert. For server.
  * client\_cert.p12 PKCS#12 container. For client.
    * certificate
    * cacert
    * key
  * key.pem key for cert.pem. For server.

Dump key

```
openssl rsa -in key.pem -text
```

Dump certificate

```
openssl x509 -in cert.pem -text
```

# TLS cipher suite #

## Standard "ssl" module ##

Add the "ciphers" parameter to ssl.wrap\_socket() call in standalone.py.