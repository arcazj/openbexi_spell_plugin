#!/usr/bin/env bash
# Ephemeral encrypted swap for the dedicated GitHub-hosted experiment only.
# Never changes fstab, swappiness, existing swap, production nodes or containers.
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_ENVIRONMENT:-}" == github-hosted && "${RUNNER_OS:-}" == Linux ]] || {
  echo 'Refusing swap setup outside a GitHub-hosted Linux runner' >&2; exit 2;
}
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]+$ && "${GITHUB_RUN_ATTEMPT:-}" =~ ^[0-9]+$ && $# -gt 0 ]] || exit 2
[[ $(id -u) -ne 0 ]] || { echo 'Run as the ordinary hosted runner account' >&2; exit 2; }
[[ $(wc -l < /proc/swaps) -eq 1 ]] || {
  echo 'Existing host swap is present; refusing to alter or use it' >&2; exit 2;
}
command -v cryptsetup >/dev/null
command -v losetup >/dev/null
export OPENBEXI_MEMORY_SWAP_NAME="openbexi-v08-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
mapper="/dev/mapper/${OPENBEXI_MEMORY_SWAP_NAME}"
[[ ! -e "$mapper" ]] || exit 2
folder=$(mktemp -d "${RUNNER_TEMP:?}/openbexi-memory-swap.XXXXXXXX")
file="$folder/encrypted.swap"
loop=''
opened=0
active=0
cleanup() {
  status=$?
  trap - EXIT INT TERM
  # Fail closed: do not detach or delete backing storage if swapoff fails.
  if [[ $active == 1 ]]; then
    if ! sudo -n swapoff "$mapper"; then echo 'Swap cleanup failed; backing storage retained' >&2; exit 1; fi
  fi
  if [[ $opened == 1 ]]; then sudo -n cryptsetup close "$OPENBEXI_MEMORY_SWAP_NAME" || exit 1; fi
  if [[ -n "$loop" ]]; then sudo -n losetup -d "$loop" || exit 1; fi
  rm -f -- "$file"
  rmdir -- "$folder"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Keep backing storage private without changing the qualification command's
# umask: its generated read-only code is mounted into a different container UID.
# A global 077 makes those imports unreadable (including the independent DSS).
# Full allocation avoids sparse-file surprises and bounds disk use to 2 GiB.
(umask 077; dd if=/dev/zero of="$file" bs=1M count=2048 conv=fsync status=none)
loop=$(sudo -n losetup --find --show "$file")
sudo -n cryptsetup open --type plain --cipher aes-xts-plain64 --key-size 256 --key-file /dev/urandom "$loop" "$OPENBEXI_MEMORY_SWAP_NAME"
opened=1
sudo -n mkswap "$mapper" >/dev/null
sudo -n swapon "$mapper"
active=1
# Command executes as the ordinary runner, never as root. The random key is
# held by dm-crypt, never saved to disk, logs or artifacts.
"$@"
