#!/usr/bin/env bash
# Generate a throwaway test key for GPG transform tests.
# Invoked from the test fixture at runtime against a tmp_path gnupghome.
# Uses gpg defaults (RSA, sign+encrypt+auth usage) with no passphrase.
set -euo pipefail
GNUPGHOME="${1:?missing gnupghome argument}"
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"
gpg --homedir "$GNUPGHOME" --batch --pinentry-mode loopback --passphrase '' \
    --quick-gen-key 'test@mountainash.example' default default never
