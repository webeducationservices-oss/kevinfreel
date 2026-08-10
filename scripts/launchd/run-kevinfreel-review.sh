#!/bin/bash
# Bootstrap for the weekly Kevin Freel neighborhood review.
#
# WHY THIS LIVES OUTSIDE ~/Desktop:
# macOS TCC blocks LaunchAgents from reading ~/Desktop, ~/Documents and
# ~/Downloads unless the executing binary has Full Disk Access. The first
# version of this lived in the repo on the Desktop, so launchd could not even
# open it: exit 126, "Operation not permitted", and an EMPTY log. A silent
# failure is the worst outcome for a job whose whole safety net is "Justin
# notices the email stopped", so this bootstrap sits in a location launchd can
# always read and it ALWAYS writes a line, even when it cannot reach the repo.

set -uo pipefail

REPO="/Users/justinbabcock/Desktop/Websites/kevinfreel"
INNER="$REPO/scripts/run_neighborhood_review.sh"
LOG="$HOME/Library/Logs/kevinfreel-neighborhood-review.log"
STAMP="$HOME/Library/Application Support/WES/last-review-run"

mkdir -p "$(dirname "$LOG")"
echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') bootstrap ===" >> "$LOG"

# Probe Desktop access before anything else, so a TCC denial is unmistakable
# instead of surfacing as a confusing downstream error.
if ! cat "$INNER" > /dev/null 2>&1; then
  {
    echo "FATAL: cannot read $INNER"
    echo "Almost certainly macOS Full Disk Access. A LaunchAgent cannot read"
    echo "~/Desktop unless the executing binary is granted it."
    echo "Fix: System Settings > Privacy & Security > Full Disk Access > add /bin/bash"
    echo "Then: launchctl kickstart -k gui/$(id -u)/com.wes.kevinfreel-neighborhood-review"
    echo "NO EMAIL WAS SENT."
  } >> "$LOG"
  echo "tcc-denied $(date '+%Y-%m-%d %H:%M:%S')" > "$STAMP" 2>/dev/null
  exit 78   # EX_CONFIG
fi

bash "$INNER"
STATUS=$?
echo "bootstrap exit $STATUS" >> "$LOG"
echo "$([ $STATUS -eq 0 ] && echo ok || echo "fail-$STATUS") $(date '+%Y-%m-%d %H:%M:%S')" > "$STAMP" 2>/dev/null
exit $STATUS
