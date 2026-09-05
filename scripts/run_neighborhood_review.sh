#!/bin/bash
# Weekly neighborhood review email. Invoked by launchd via the bootstrap at
# ~/Library/Application Support/WES/run-kevinfreel-review.sh
#
#   Manual run:  bash scripts/run_neighborhood_review.sh
#   Log:         ~/Library/Logs/kevinfreel-neighborhood-review.log
#
# WHY THE STAGING DANCE
# macOS TCC grants Full Disk Access per BINARY, not per process tree. /bin/bash
# has been granted it, so bash can read this repo on the Desktop. Python has
# NOT, and a child process does not inherit the grant: the first working
# version got as far as running python, which then died with
# "Operation not permitted" trying to open its own .py file.
#
# Rather than grant FDA to the Homebrew python too (its path is version-pinned,
# so a brew upgrade would silently break the job), bash does every Desktop read
# and write, and python runs entirely inside ~/Library/Application Support,
# which is not TCC-protected. Keys are sourced by bash and inherited through the
# environment, so the keys file is never copied anywhere.

set -uo pipefail

REPO="/Users/justinbabcock/Desktop/Websites/kevinfreel"
KEYS="/Users/justinbabcock/Desktop/Websites/.env.keys"
PY="$HOME/.venvs/kevinfreel/bin/python"
STAGE="$HOME/Library/Application Support/WES/stage"
LOG="$HOME/Library/Logs/kevinfreel-neighborhood-review.log"

mkdir -p "$(dirname "$LOG")"
echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') ===" >> "$LOG"

fail() { echo "ABORT: $1" >> "$LOG"; exit 1; }

[ -f "$KEYS" ] || fail "keys file not readable: $KEYS (is /bin/bash granted Full Disk Access?)"
[ -x "$PY" ]   || fail "venv python missing: $PY"
[ -d "$REPO" ] || fail "repo not readable: $REPO"

# shellcheck disable=SC1090
set -a; source "$KEYS"; set +a
[ -n "${ANTHROPIC_API_KEY:-}" ] || fail "ANTHROPIC_API_KEY missing"
[ -n "${RESEND_API_KEY:-}" ]    || fail "RESEND_API_KEY missing"

# Stage the three files python needs, outside the protected directory.
rm -rf "$STAGE"
mkdir -p "$STAGE/scripts" "$STAGE/data" || fail "cannot create staging dir"
cp "$REPO/scripts/email_neighborhood_review.py" "$STAGE/scripts/" || fail "cannot stage script"
cp "$REPO/data/south-tampa-neighborhoods.json"  "$STAGE/data/"    || fail "cannot stage data"
cp "$REPO/data/neighborhood-prices.json"        "$STAGE/data/"    || fail "cannot stage prices"

cd "$STAGE" || fail "cannot enter staging dir"
"$PY" scripts/email_neighborhood_review.py >>"$LOG" 2>&1
STATUS=$?

# A draft is only written when a neighborhood is missing framing, which after
# the initial backfill means a newly added one. Copy it back so it isn't lost.
if [ $STATUS -eq 0 ] && ! cmp -s "$STAGE/data/south-tampa-neighborhoods.json" "$REPO/data/south-tampa-neighborhoods.json"; then
  cp "$STAGE/data/south-tampa-neighborhoods.json" "$REPO/data/" \
    && echo "NOTE: data file changed and was copied back. Commit it and rerun build_neighborhoods.py." >> "$LOG"
fi

rm -rf "$STAGE"
echo "exit $STATUS" >> "$LOG"
exit $STATUS
