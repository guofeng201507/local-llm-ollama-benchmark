#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:A:h}
OLLAMA_BIN="$SCRIPT_DIR/vendor/nanbeige-ollama/ollama"

if [[ ! -x "$OLLAMA_BIN" ]]; then
  print -u2 "Nanbeige Ollama binary not found: $OLLAMA_BIN"
  exit 1
fi

export OLLAMA_HOST=${OLLAMA_HOST:-127.0.0.1:11435}
exec "$OLLAMA_BIN" serve
