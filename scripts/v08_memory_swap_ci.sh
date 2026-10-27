#!/usr/bin/env bash
# Explicit hosted-runner preparation; encrypted-device lifecycle stays separate.
set -euo pipefail
exec python "$(dirname "$0")/v08_memory_swap_runner.py" "$@"
