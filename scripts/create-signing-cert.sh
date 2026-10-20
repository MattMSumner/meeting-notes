#!/bin/sh
# One-time setup: creates a self-signed code signing certificate in the login keychain.
#
# macOS ties privacy permissions (like System Audio Recording) to an app's signing
# identity. Ad-hoc signatures change on every build, so permissions break after each
# rebuild. Signing with this certificate keeps the identity stable across builds.
# It is only trusted on this Mac, which is all a personal tool needs.
#
# Usage: scripts/create-signing-cert.sh ["certificate name"]
# The trust step at the end asks for your login password.
set -e

NAME="${1:-meeting-notes local signing}"
KEYCHAIN="$HOME/Library/Keychains/login.keychain-db"

if security find-identity -v -p codesigning | grep -q "\"$NAME\""; then
  echo "Signing identity \"$NAME\" already exists."
  exit 0
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/cert.cnf" <<EOF
[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = $NAME
[ext]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature
extendedKeyUsage = critical,codeSigning
EOF

/usr/bin/openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
  -config "$TMP/cert.cnf" -keyout "$TMP/key.pem" -out "$TMP/cert.pem" 2>/dev/null
/usr/bin/openssl pkcs12 -export -inkey "$TMP/key.pem" -in "$TMP/cert.pem" \
  -out "$TMP/identity.p12" -passout pass:import

# -T lets codesign use the key without a keychain prompt on every build.
security import "$TMP/identity.p12" -k "$KEYCHAIN" -P import -T /usr/bin/codesign
echo "Trusting the certificate for code signing (asks for your password)..."
security add-trusted-cert -r trustRoot -p codeSign -k "$KEYCHAIN" "$TMP/cert.pem"

security find-identity -v -p codesigning | grep "\"$NAME\""
echo "Created signing identity \"$NAME\"."
