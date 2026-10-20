#!/bin/sh
# Runs the Swift unit tests. With only the Command Line Tools installed (no Xcode),
# Swift Testing's macro plugin lives in a folder the build doesn't search, so point at it.
set -e
cd "$(dirname "$0")"
PLUGINS=/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing
if [ -d "$PLUGINS" ]; then
  exec swift test -Xswiftc -plugin-path -Xswiftc "$PLUGINS" "$@"
fi
exec swift test "$@"
