#!/bin/bash
# Wrapper for the weekly neighborhood review email, invoked by launchd.
#
# launchd runs jobs with a bare environment and no login shell, so this script
# supplies everything the Python needs: the venv interpreter and the API keys.
# Keys are read from .env.keys at run time and never leave this machine.
#
#   Manual run:  bash scripts/run_neighborhood_review.sh
#   Log:         ~/Library/Logs/kevinfreel-neighborhood-review.log

set -uo pipefail

REPO="/Users/justinbabcock/Desktop/Websites/kevinfreel"
KEYS="/Users/justinbabcock/Desktop/Websites/.env.keys"
PY="$HOME/.venvs/kevinfreel/bin/python"
LOG="$HOME/Library/Logs/kevinfreel-neighborhood-review.log"

mkdir -p "$(dirname "$LOG")"
echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') ===" >> "$LOG"

fail() { echo "ABORT: $1" >> "$LOG"; exit 1; }

[ -f "$KEYS" ] || fail "keys file not found: $KEYS"
[ -x "$PY" ]   || fail "venv python not found: $PY (recreate: python3 -m venv ~/.venvs/kevinfreel && ~/.venvs/kevinfreel/bin/pip install anthropic pydantic)"
cd "$REPO"     || fail "repo not found: $REPO"

# shellcheck disable=SC1090
set -a; source "$KEYS"; set +a

[ -n "${ANTHROPIC_API_KEY:-}" ] || fail "ANTHROPIC_API_KEY missing from keys file"
[ -n "${RESEND_API_KEY:-}" ]    || fail "RESEND_API_KEY missing from keys file"

# Pull first so the draft commit below doesn't race the listings cron.
git pull --quiet --rebase 2>>"$LOG"

"$PY" scripts/email_neighborhood_review.py >>"$LOG" 2>&1
STATUS=$?

# A draft only gets written when a neighborhood was missing framing. Commit it
# so the review form can load it.
if [ $STATUS -eq 0 ] && [ -n "$(git status --porcelain data/south-tampa-neighborhoods.json)" ]; then
  git add data/south-tampa-neighborhoods.json
  git commit --quiet -m "Draft neighborhood framing for the week of $(date +%Y-%m-%d)" >>"$LOG" 2>&1
  git push --quiet >>"$LOG" 2>&1 && echo "pushed draft" >> "$LOG"
fi

echo "exit $STATUS" >> "$LOG"
exit $STATUS
