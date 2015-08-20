This is a note by pywebsocket developers for catching up changes on the spec and tracking discussion on HyBi. This may also be useful for people who are interested in WebSocket protocol design to quickly catch up the history of discussion on HyBi and understand what/why/when a certain decision has been made.

# Protocol support status of pywebsocket #

pywebsocket supports the following protocols.

  * [RFC 6455 The WebSocket Protocol](http://tools.ietf.org/html/rfc6455)
    * was also known as [draft-ietf-hybi-thewebsocketprotocol-17](http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-17) (Version 13)
  * [draft-ietf-hybi-thewebsocketprotocol-12](http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-12) (Version 8)
  * [draft-ietf-hybi-thewebsocketprotocol-00](http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-00)
    * equivalent to [draft-hixie-thewebsocketprotocol-76](http://tools.ietf.org/html/draft-hixie-thewebsocketprotocol-76)

and the following extension.

  * [WebSocket Per-message Compression (permessage-deflate)](http://tools.ietf.org/html/draft-ietf-hybi-permessage-compression-18)
  * [WebSocket Per-message Compression (permessage-compress)](http://tools.ietf.org/html/draft-ietf-hybi-permessage-compression-04) (Deprecated)
    * draft-ietf-hybi-permessage-compression version 04 and prior specified permessage-compress extension
    * draft-ietf-hybi-permessage-compression version 05 and later specifies permessage-deflate extension
  * [WebSocket Per-frame Compression (perframe-compress)](http://tools.ietf.org/html/draft-ietf-hybi-websocket-perframe-compression-04) (Deprecated)
  * [WebSocket Per-frame Compression (deflate-frame)](http://tools.ietf.org/html/draft-tyoshino-hybi-websocket-perframe-deflate-06) (Deprecated)

# Official working drafts #

## HyBi 17 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-17)
  * [Diff from 16](http://tools.ietf.org/rfcdiff?url2=draft-ietf-hybi-thewebsocketprotocol-16)

Note
  * Only editorial changes
  * Sec-WebSocket-Version value is still 13 and this must be the version for RFC

## HyBi 16 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-16)
  * [Diff from 15](http://tools.ietf.org/rfcdiff?url2=draft-ietf-hybi-thewebsocketprotocol-16)

Note
  * Only editorial changes

## HyBi 15 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-15)
  * [Diff from 14](http://tools.ietf.org/rfcdiff?url2=draft-ietf-hybi-thewebsocketprotocol-15)

Semantic changes
  * If servers doesn't support the requested version, they MUST respond with Sec-WebSocket-Version headers containing all available versions.
  * The servers MUST close the connection upon receiving a non-masked frame with status code of 1002.
  * The clients MUST close the connection upon receiving a masked frame with status code of 1002.

Note
  * Sec-WebSocket-Version is still 13.

## HyBi 14 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-14)
  * [Diff from 13](http://tools.ietf.org/rfcdiff?url2=draft-ietf-hybi-thewebsocketprotocol-14)

Semantic changes
  * Extension values in extension-param could be quoted-string in addition to token.
  * Clarify the way to support multiple versions of WebSocket protocol.
  * Payload length MUST be encoded in minimal number of bytes.
  * WebSocket MUST support TLS.
  * Sec-WebSocket-Key and Sec-WebSocketAccept header field MUST NOT appear more than once.
  * Sec-WebSocket-Extensions and Sec-WebSocket-Protocol header filed MAY appear multiple times in requests, but it MUST NOT appear more than once in responses.
  * Sec-WebSocket-Version header filed MAY appear multiple times in responses, but it MUST NOT appear more than once in requests.
  * Status code 1007 was changed.

Note
  * Sec-WebSocket-Version is still 13.

## HyBi 13 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-13)
  * [Diff from 12](http://tools.ietf.org/rfcdiff?url2=draft-ietf-hybi-thewebsocketprotocol-13)

Semantic changes
  * Sec-WebSocket-Version is 13.
  * Clients must fail the connection on receiving a subprotocol indication that was not present in the client requests in the opening handshake.
  * Status Codes was changes(Change 1004 as reserved, and add 1008, 1009, 1010).

Note
  * Now spec allow to use WWW-Authenticate header and 401 status explicitly.
  * Servers might redirect the client using a 3xx status code, but client are not required to follow them.
  * Clients' reconnection on abnormal closure must be delayed (between 0 and 5 seconds is a reasonable initial delay, and subsequent reconnection should be delayed longer by exponential backoff.

## HyBi 12 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-12.txt)
  * [Diff from 11](http://tools.ietf.org/rfcdiff?url2=draft-ietf-hybi-thewebsocketprotocol-12)

### Change ###

Note
  * Only editorial changes
  * Sec-WebSocket-Version value is still 8.

## HyBi 11 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-11.txt)
  * [Diff from 10](http://tools.ietf.org/rfcdiff?url2=draft-ietf-hybi-thewebsocketprotocol-11)

### Change ###

Semantic changes
  * Sec-WebSocket-Origin -> Origin
  * Servers send all supported protocol numbers in Sec-WebSocket-Version header.

Note
  * Sec-WebSocket-Version value is still 8, and 9/10/11 were reserved but were not and will not be used.

## HyBi 10 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-10.txt)
  * [Diff from 09](http://tools.ietf.org/rfcdiff?url2=draft-ietf-hybi-thewebsocketprotocol-10)

### Change ###

Semantic changes
  * Status code 1007.
  * Receiving strings including invalid UTF-8 result in Fail.

Note
  * Sec-WebSocket-Version value is still 8.

## HyBi 09 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-09.txt)
  * [Diff from 08](http://tools.ietf.org/rfcdiff?url2=draft-ietf-hybi-thewebsocketprotocol-09)

### Change ###

Semantic changes
  * On receiving a frame with any of RSV1-3 raised but no extension negotiated, Fail the WebSocket Connection.
    * It seems that unknown opcode will also result in Fail in HyBi 10. (TBD)

Note
  * Sec-WebSocket-Version value is still 8.

## HyBi 08 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-08.txt)
  * [Diff from 07](http://tools.ietf.org/rfcdiff?url2=draft-ietf-hybi-thewebsocketprotocol-08)

Semantic changes
  * Absolute path is now allowed for resource.
  * extension parameter is token.
  * Sec-WebSocket-Protocol from server to client is token.
  * Status code 1005 and 1006 are added, and all codes are unsigned.
  * Internal error results in 1006.
  * HTTP fallback status codes are clarified.

## HyBi 07 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-07.txt)
  * [Diff from 06](http://tools.ietf.org/rfcdiff?url2=draft-ietf-hybi-thewebsocketprotocol-07)

## HyBi 06 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-06.txt)
  * [Diff from 05](http://tools.ietf.org/rfcdiff?url2=draft-ietf-hybi-thewebsocketprotocol-06)

Major changes
  * "Connection" header must INCLUDE "Upgrade", rather than is equal to "Upgrade"

## HyBi 05 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-05.txt)
  * [Diff from 04](http://tools.ietf.org/rfcdiff?url2=draft-ietf-hybi-thewebsocketprotocol-05)

### Change ###

Major changes
  * Removed Sec-WebSocket-Nonce
  * Changed masking : SHA-1, client nonce, server nonce, CSPRNG -> CSPRNG only
  * Specified the body of close frame explicitly
  * ABNF fix for origin and protocol
  * Added detailed Sec-WebSocket-Extensions format specification

Typos, remanet removal
  * Removed all occurrence of Sec-WebSocket-Location
  * Added IANA Sec-WebSocket-Accept section

Trivial changes
  * The value of Sec-WebSocket-Version is now 5

## HyBi 04 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-04.txt)

### Change ###

Major changes
  * Added frame masking
  * Changed opening handshake
    * Sec-WebSocket-Key1, Sec-WebSocket-Key2, key3, response -> Sec-WebSocket-Key, Sec-WebSocket-Nonce, Sec-WebSocket-Accept)
  * Added Sec-WebSocket-Extensions for extension negotiation
  * Upgrade header is now case-insensitive (HTTP compliant)
  * Flipped MORE bit and renamed it to FIN bit

Tiny changes
  * Renamed Sec-WebSocket-Draft to Sec-WebSocket-Version
  * Renamed Origin to Sec-WebSocket-Origin
  * Added ABNF (one used in HTTP RFC2616) clarification to Sec-WebSocket-Protocol
  * Changed subprotocols separator from SP to ','
  * Removed Sec-WebSocket-Location

### Library dependency ###

Introduced
  * BASE64
  * SHA-1

Eliminated
  * MD5

## HyBi 03 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-03.txt)

### Change ###

  * Added one known extension "compression"
  * Added close frame body matching step to closing handshake
    * To distinguish close frames among virtual channels in multiplexed connection

### Library dependency ###

Introduced
  * DEFLATE

### Note ###

  * The value of Sec-WebSocket-Draft is still 2

## HyBi 02 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-02.txt)

### Change ###

  * Added /defer cookies/ flag
  * Added Sec-WebSocket-Draft with a value of 2

## HyBi 01 ##

  * [Spec](http://tools.ietf.org/id/draft-ietf-hybi-thewebsocketprotocol-01.txt)

### Change ###

  * Changed frame format
  * Added extension mechanism (no negotiation yet)

## Hixie 76 (HyBi 00) ##

  * [HyBi 00](http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-00)
  * [Hixie 76](http://tools.ietf.org/html/draft-hixie-thewebsocketprotocol-76)

### Change ###

  * Added challenge/response handshaking using binary data
  * Added closing handshake

### Library dependency ###

Introduced
  * MD5

## Hixie 75 ##

  * [Spec](http://tools.ietf.org/html/draft-hixie-thewebsocketprotocol-75)

# Extension spec drafts #

## Compression ##

### ietf 00 ###

  * [Spec](http://tools.ietf.org/html/draft-ietf-hybi-websocket-perframe-compress-00)

### websocket-perframe-deflate-06 ###

  * [Spec](http://tools.ietf.org/html/draft-tyoshino-hybi-websocket-perframe-deflate-06)

### websocket-perframe-deflate-05 ###

  * [Spec](http://tools.ietf.org/html/draft-tyoshino-hybi-websocket-perframe-deflate-05)

### websocket-perframe-deflate-04 ###

  * [Spec](http://tools.ietf.org/html/draft-tyoshino-hybi-websocket-perframe-deflate-04)

### websocket-perframe-deflate-03 ###

  * [Spec](http://tools.ietf.org/html/draft-tyoshino-hybi-websocket-perframe-deflate-03)

### websocket-perframe-deflate-02 ###

  * [Spec](http://tools.ietf.org/html/draft-tyoshino-hybi-websocket-perframe-deflate-02)

### websocket-perframe-deflate-01 ###

  * [Spec](http://tools.ietf.org/html/draft-tyoshino-hybi-websocket-perframe-deflate-01)

### websocket-perframe-deflate-00 ###

  * [Spec](http://tools.ietf.org/html/draft-tyoshino-hybi-websocket-perframe-deflate-00)

## A Multiplexing Extension for WebSockets ##

### ietf 01 ###

  * [Spec](http://tools.ietf.org/html/draft-ietf-hybi-websocket-multiplexing-01)

### ietf 00 ###

  * [Spec](http://tools.ietf.org/html/draft-ietf-hybi-websocket-multiplexing-00)

### google-mux-03 ###

  * [Spec](http://tools.ietf.org/html/draft-tamplin-hybi-google-mux-03)

### google-mux-02 ###

  * [Spec](http://tools.ietf.org/html/draft-tamplin-hybi-google-mux-02)

### google-mux-01 ###

  * [Spec](http://tools.ietf.org/html/draft-tamplin-hybi-google-mux-01)

### google-mux-00 ###

  * [Spec](http://tools.ietf.org/html/draft-tamplin-hybi-google-mux-00)


# Rationale #

Contents placed here has been merged into [FAQ on the IETF HyBi WG site](http://trac.tools.ietf.org/wg/hybi/trac/wiki/FAQ).

# Other proposals #

  * http://tools.ietf.org/id/draft-abarth-thewebsocketprotocol-01.txt Opening handshake with CONNECT method, AES based frame masking by Adam Barth
  * http://tools.ietf.org/html/draft-montenegro-hybi-upgrade-hello-handshake-00 Gabriel's proposal
  * http://www.whatwg.org/specs/web-socket-protocol/ Last proposal Hixie published before he took over editor to Ian Fette.

# References/Tools #

  * [HyBi mailing list archive](http://www.ietf.org/mail-archive/web/hybi/current/maillist.html)
  * [IETF datatracker](https://datatracker.ietf.org/doc/draft-ietf-hybi-thewebsocketprotocol/history/) Useful for getting side-by-side diff between drafts
  * [Latest draft on IETF Subversion](http://trac.tools.ietf.org/wg/hybi/trac/log/websocket/draft-ietf-hybi-thewebsocketprotocol.xml)
  * [Proposal list on HyBi wiki](http://trac.tools.ietf.org/wg/hybi/trac/wiki/HandshakeProposals)