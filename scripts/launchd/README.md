# Weekly neighborhood review — scheduling

The job that emails Kevin his neighborhood-of-the-week. These files are the
tracked copies; the live ones are at:

    ~/Library/Application Support/WES/run-kevinfreel-review.sh
    ~/Library/LaunchAgents/com.wes.kevinfreel-neighborhood-review.plist

## The macOS gotcha that cost a week

**A LaunchAgent cannot read `~/Desktop`, `~/Documents` or `~/Downloads`** unless
the executing binary has Full Disk Access. This repo lives on the Desktop, so
the first version of this job (wrapper inside the repo) failed with exit 126 and
`Operation not permitted` before running a single line. The log file was never
even created, so the failure was completely silent. Kevin got nothing for a week.

Two fixes, both needed:

1. **The bootstrap lives outside `~/Desktop`** so launchd can always read and run
   it. It probes repo access first and writes an explicit FATAL line when TCC
   denies it, instead of dying invisibly.
2. **Grant Full Disk Access to `/bin/bash`**
   System Settings > Privacy & Security > Full Disk Access > `+` > Cmd-Shift-G >
   `/bin/bash`. This is the part a human has to do; it cannot be scripted.

3. **TCC is granted per BINARY, and children do NOT inherit it.** Granting bash
   FDA got bash into the repo, and then python died with the same
   "Operation not permitted" opening its own `.py` file. Granting the Homebrew
   python FDA too would work but its path is version-pinned
   (`.../python@3.14/3.14.5/...`), so a `brew upgrade` would silently break the
   job again. Instead `run_neighborhood_review.sh` has bash do every Desktop
   read and write, stages the three files python needs into
   `~/Library/Application Support/WES/stage` (not TCC-protected), and runs
   python there. Keys are sourced by bash and inherited via the environment, so
   the keys file is never copied out of the Desktop.

Then verify:

    launchctl kickstart -k gui/$(id -u)/com.wes.kevinfreel-neighborhood-review
    tail ~/Library/Logs/kevinfreel-neighborhood-review.log

## Checking on it

    # last outcome, at a glance
    cat "$HOME/Library/Application Support/WES/last-review-run"

    # full log
    tail -30 ~/Library/Logs/kevinfreel-neighborhood-review.log

    # is it scheduled?
    launchctl print gui/$(id -u)/com.wes.kevinfreel-neighborhood-review | grep -iE "exit code|runs ="

## Reinstall

    launchctl bootout gui/$(id -u)/com.wes.kevinfreel-neighborhood-review
    cp scripts/launchd/run-kevinfreel-review.sh "$HOME/Library/Application Support/WES/"
    cp scripts/launchd/com.wes.kevinfreel-neighborhood-review.plist "$HOME/Library/LaunchAgents/"
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.wes.kevinfreel-neighborhood-review.plist
