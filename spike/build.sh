#!/bin/sh
# Builds the spike with Info.plist embedded in the binary (required for the
# NSAudioCaptureUsageDescription permission), then ad-hoc signs it.
set -e
cd "$(dirname "$0")"
swiftc -O -swift-version 5 main.swift -o tapspike \
  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker Info.plist
codesign --force --sign - --identifier com.mattmsumner.tapspike tapspike
echo "built spike/tapspike"
