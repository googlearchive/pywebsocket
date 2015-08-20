# Benchmark using benchmark.html #

  * Checkout the latest pywebsocket
```
$ svn checkout https://pywebsocket.googlecode.com/svn/trunk
```
  * Open `setup.py` using some editor and set `_USE_FAST_MASKING` to `True`
  * Build the extension
```
$ ./setup.py build_ext --inplace
```
  * Move to `src/`
```
$ cd src
```
  * Launch pywebsocket
```
$ PYTHONPATH=. python mod_pywebsocket/standalone.py -p <port> -d example
```
  * Navigate your browser to `localhost:<port>/benchmark.html`

# Benchmark using console.html #

  * Open console.html
  * Connect to the resource "`ws://<host>:<port>/echo_noext`".
  * Check "Show time stamp"
  * Specify some big file and click send file.