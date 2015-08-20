# Cross site initiation #

  * wss://foo.com:8444 from https://foo.com:8443
    * Aurora 17.0a2 (2012-09-25): allowed
    * Chrome 23.0.1271.0 canary: allowed
  * ws://foo.com:8080 from https://foo.com:8443
    * Aurora 17.0a2 (2012-09-25): SecurityError
    * Chrome 23.0.1271.0 canary: allowed
      * http://code.google.com/p/chromium/issues/detail?id=85271
      * https://bugs.webkit.org/show_bug.cgi?id=89068
  * wss://foo.com:8443 from http://foo.com:8080
    * Aurora 17.0a2 (2012-09-25): allowed
    * Chrome 23.0.1271.0 canary: allowed