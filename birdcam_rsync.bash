#!/usr/bin/env bash
set -euo pipefail

############################################
# Usage:
#   birdcam_rsync_to_pi5.bash PI5_HOST DEST OUTBOX HOLD
#
# Example:
#   ./birdcam_rsync_to_pi5.bash \
#       user@host \
#       /birdcam_dropbox/ \
#       /birdcam/outbox \
#       /birdcam/holding
############################################

if [[ $# -ne 4 ]]; then
  echo "Usage: $0 PI5_HOST DEST OUTBOX HOLD"
  exit 1
fi

PI5_HOST="$1"
DEST="$2"
OUTBOX="$3"
HOLD="$4"

mkdir -p "$OUTBOX" "$HOLD"

# Ensure DEST ends with /
[[ "$DEST" != */ ]] && DEST="${DEST}/"

# Prevent overlapping runs
LOCK="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/birdcam_rsync.lock"
exec 9>"$LOCK"
flock -n 9 || exit 0

############################################
# Determine whether a file is stable
#  - size unchanged over 1 second
#  - older than 120 seconds
############################################
is_stable() {
  local f="$1"
  [[ -f "$f" ]] || return 1

  local s1 s2
  s1=$(stat -c '%s' "$f") || return 1
  sleep 1
  s2=$(stat -c '%s' "$f") || return 1
  [[ "$s1" == "$s2" ]] || return 1

  local age=$(( $(date +%s) - $(stat -c '%Y' "$f") ))
  [[ $age -ge 120 ]]
}

############################################
# Rsync options
############################################
RSYNC_OPTS=(
  -av
  --partial
  --inplace
  --protect-args
  --timeout=30
)

############################################
# Main loop
############################################

mapfile -d '' FILES < <(
  find "$OUTBOX" -maxdepth 1 -type f \
    \( -iname '*.mp4' -o -iname '*.jpg' \) \
    -print0
)

for f in "${FILES[@]}"; do
  if is_stable "$f"; then
    base=$(basename "$f")

    echo "Transferring $base ..."

    if rsync "${RSYNC_OPTS[@]}" "$f" "${PI5_HOST}:${DEST}${base}"; then

      # Size verification (cheap sanity check)
      src_size=$(stat -c '%s' "$f")
      dst_size=$(ssh "$PI5_HOST" "stat -c '%s' '${DEST}${base}'" 2>/dev/null || echo "")

      if [[ "$src_size" == "$dst_size" ]]; then
        echo "Verified $base — moving to holding."
        mv -n "$f" "$HOLD/$base"
      else
        echo "WARNING: Size mismatch for $base — not moving to holding."
      fi
    else
      echo "Rsync failed for $base — will retry later."
    fi
  fi
done