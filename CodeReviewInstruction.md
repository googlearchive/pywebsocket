# Create and upload a patch #

Install [depot\_tools](http://dev.chromium.org/developers/how-tos/install-depot-tools) for Chromium project

Make a change on the trunk and create a change list by
```
$ gcl change
```

Upload the change list to the [code review site](https://codereview.appspot.com/)
```
$ gcl upload <change list name>
```

Once got LGTM, commit by
```
$ gcl commit <change list name>
```

# Run all unit tests #

cd to src/ directory, and run
```
$ python test/run_all.py --log_level debug -- -v
```

# Check coding style #

Run [pep8](https://pypi.python.org/pypi/pep8)
```
$ pep8 --repeat **/*.py
```

# Release #

Update version in src/setup.py, and commit.

Create a new tag
```
$ svn cp https://pywebsocket.googlecode.com/svn/trunk https://pywebsocket.googlecode.com/svn/tags/pywebsocket-version
```

Announce on the pywebsocket group

# Update DEPS in Chromium #

Update the revision number part in the rule for pywebsocket

# Update pywebsocket copy in the WebKit repository #

http://trac.webkit.org/wiki/pywebsocket%3A%20a%20WebSocket%20server%20for%20layout%20tests