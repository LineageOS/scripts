#!/bin/bash

if ! cd "$1"; then
    echo "USAGE: $0 PATH"
    exit 1
fi

for x in platform media shared; do
    echo ${x}_key_release=\"$(openssl x509 -pubkey -noout -in $x.x509.pem | grep -v '-' | tr -d '\n')\"
    echo ${x}_cert_release=\"$(openssl x509 -outform der -in $x.x509.pem | xxd -p  | tr -d '\n')\"
done

echo release_key=\"$(openssl x509 -pubkey -noout -in releasekey.x509.pem | grep -v '-' | tr -d '\n')\"
echo release_cert=\"$(openssl x509 -outform der -in releasekey.x509.pem | xxd -p  | tr -d '\n')\"
