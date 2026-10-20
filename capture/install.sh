#!/bin/sh
# Builds notes-capture as a signed NotesCapture.app in capture/build/, then runs
# `notes-capture check`.
#
# Why an .app with a stable signature: macOS ties the System Audio Recording permission
# to the app's identity. A bare binary with an ad-hoc signature gets silently denied after
# every rebuild (see the spike results in plan.md). Create the signing identity once with
# scripts/create-signing-cert.sh.
#
# Why run check: the first run after a rebuild records zeros. Doing it here means that
# throwaway run never happens during a meeting.
set -e
cd "$(dirname "$0")"

IDENTITY="${SIGN_IDENTITY:-meeting-notes local signing}"
APP=build/NotesCapture.app

if ! security find-identity -v -p codesigning | grep -q "\"$IDENTITY\""; then
  echo "Signing identity \"$IDENTITY\" not found. Run scripts/create-signing-cert.sh first." >&2
  exit 1
fi

swift build -c release
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp Info.plist "$APP/Contents/Info.plist"
cp "$(swift build -c release --show-bin-path)/notes-capture" "$APP/Contents/MacOS/notes-capture"
codesign --force --sign "$IDENTITY" "$APP"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"
echo "Installed $(pwd)/$APP"

"$APP/Contents/MacOS/notes-capture" check
