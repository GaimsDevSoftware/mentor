#!/usr/bin/env bash
# canary_deploy.sh — auto-rollback watchdog after a self-coder merge.
#
# Started DETACHED by self_coder.apply_proposal so it survives the restart it
# triggers. Restarts the service, health-checks for up to N seconds; if the app
# doesn't come up, reverts to the previous commit and restarts again — so a bad
# self-edit can NEVER brick the app (a bricked app can't fix itself).
#
# The rollback uses `git reset --hard <prev_commit>` ONLY against the commit
# explicitly passed in by self_coder (the commit the working tree was on BEFORE
# the merge). The script is only ever launched from a user-clicked "Apply" in
# /manage; it does nothing until that happens.
#
# Args: <repo> <prev_commit> <health_url> <service_name> <proposal_id>
set -u
REPO="${1:?repo}"; PREV="${2:?prev}"; HEALTH="${3:?health}"; SERVICE="${4:?service}"; PID="${5:?id}"
LOG="$REPO/data/self_coder/canary-$PID.log"
mkdir -p "$(dirname "$LOG")"

log(){ echo "[$(date -Iseconds)] $*" >>"$LOG"; }
restart(){ systemctl --user restart "$SERVICE" >>"$LOG" 2>&1; }

log "canary start: repo=$REPO prev=$PREV health=$HEALTH service=$SERVICE id=$PID"

# Give the parent a moment to return its HTTP response before we restart it.
sleep 2
restart

# Health-check: poll for up to ~90s
ok=0
for i in $(seq 1 30); do
  sleep 3
  if curl -fsS --max-time 4 -o /dev/null "$HEALTH"; then
    ok=1; log "health OK after ${i} attempts (~$((i*3))s)"; break
  fi
done

if [ "$ok" = "1" ]; then
  log "canary PASS - keeping the change"
  echo "pass" >"$REPO/data/self_coder/canary-$PID.result"
  exit 0
fi

log "canary FAIL - reverting to $PREV"
( cd "$REPO" && git reset --hard "$PREV" ) >>"$LOG" 2>&1
restart
echo "rollback" >"$REPO/data/self_coder/canary-$PID.result"
log "reverted; restarted at $PREV"
