#!/bin/bash

CERTS_DIR=~/.android-certs/

pushd $CERTS_DIR

for x in platform media shared; do
    echo ${x}_key_release=\"$(openssl pkcs8 -in $x.pk8 -inform DER -outform PEM -nocrypt | openssl rsa -pubout 2>/dev/null | tail -n+2 | head -n-1 | tr -d '\n')\"
    echo ${x}_cert_release=\"$(openssl x509 -outform der -in $x.x509.pem | base16)\"
done

echo release_key=\"$(openssl pkcs8 -in releasekey.pk8 -inform DER -outform PEM -nocrypt | openssl rsa -pubout 2>/dev/null | tail -n+2 | head -n-1 | tr -d '\n')\"
echo release_cert=\"$(openssl x509 -outform der -in releasekey.x509.pem | base16)\"

popd
