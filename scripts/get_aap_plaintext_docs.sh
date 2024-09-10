#!/bin/bash
set -eou pipefail

AAP_VERSION=$1

trap "rm -rf aap-docs" EXIT

rm -rf aap-product-docs-plaintext/${AAP_VERSION}

git clone --single-branch --branch ${AAP_VERSION} https://github.com/ansible/aap-docs.git

python scripts/asciidoctor-text/convert-it-all-aap.py -i aap-docs \
    -o aap-product-docs-plaintext/${AAP_VERSION} -a aap-docs/downstream/attributes/attributes.adoc

rm -rf aap-product-docs-plaintext/${AAP_VERSION}/archive