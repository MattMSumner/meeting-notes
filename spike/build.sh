#!/bin/sh
# Builds the spike as a minimal TapSpike.app, signed with a stable identity so macOS
# privacy permissions survive rebuilds, and registers it with Launch Services so it
# shows up in System Settings and `tccutil` can reset it.
#
# Run it as spike/tapspike (a wrapper that execs the binary inside the bundle).
# Create the signing identity once with scripts/create-signing-cert.sh.
set -e
cd "$(dirname "$0")"

IDENTITY="${SIGN_IDENTITY:-meeting-notes local signing}"
APP=TapSpike.app

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp Info.plist "$APP/Contents/Info.plist"

# Info.plist is also embedded in the binary, for when it runs outside the bundle.
swiftc -O -swift-version 5 main.swift -o "$APP/Contents/MacOS/tapspike" \
  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker Info.plist

if security find-identity -v -p codesigning | grep -q "\"$IDENTITY\""; then
  codesign --force --sign "$IDENTITY" "$APP"
else
  echo "warning: signing identity \"$IDENTITY\" not found; signing ad-hoc." >&2
  echo "         Permissions will break on every rebuild. Run scripts/create-signing-cert.sh." >&2
  codesign --force --sign - "$APP"
fi

/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"

cat > tapspike <<'EOF'
#!/bin/sh
exec "$(dirname "$0")/TapSpike.app/Contents/MacOS/tapspike" "$@"
EOF
chmod +x tapspike

codesign -dv "$APP" 2>&1 | grep -E "^Identifier=|^Authority=|^Signature=" || true
echo "built spike/$APP"
