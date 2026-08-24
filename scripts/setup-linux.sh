#!/usr/bin/env bash
# Compatibilidade: o fluxo único é scripts/install-linux.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install-linux.sh" "$@"
