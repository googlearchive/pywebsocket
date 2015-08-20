#Notes for developing compression spec.

# Python zlib snippets #

Sync flush (empty uncompressed block)
```
import zlib
c = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -zlib.MAX_WBITS)
b = c.compress('abcdefghijklmnopqrstuvwxyz')
b += c.flush(zlib.Z_SYNC_FLUSH)
b
```

Finish with BFINAL
```
import zlib
c = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -zlib.MAX_WBITS)
b = c.compress('abcdefghijklmnopqrstuvwxyz')
b += c.flush(zlib.Z_FINISH)
b
```

Hex printing
```
' '.join(map(lambda x: '0x%02x' % ord(x), b))
```

Decompress
```
import zlib
d = zlib.decompressobj(-zlib.MAX_WBITS)
max_length = 1
d.decompress(b, max_length)
d.decompress(d.unconsumed_tail)
d.unconsumed_tail
```