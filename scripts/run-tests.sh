#!/usr/bin/env bash
# run-tests.sh — green-CI test runner with per-file process isolation.
#
# WHY THIS EXISTS
# ---------------
# A subset of the suite imports the REAL src.database / core.database at
# collection time (they call clear_fake_database_modules() and then import the
# shipped ORM, on purpose, to test against the canonical schema). pytest imports
# every test module before running any test, so that real import evicts the
# lightweight MagicMock stub that conftest.py installs for the mock-based tests.
# The mock tests then bind to the real ORM and fail with IntegrityError /
# attribute mismatches — purely an artefact of collection ORDER, not a product
# bug. Per-test fixtures can't undo it because the symbols are already bound at
# module import.
#
# The robust fix is process isolation per file: each test file gets a fresh
# interpreter, so collection-time module state never leaks between files. That's
# what this script does. `pytest tests/` in a single process is expected to show
# the pollution failures; this runner is the canonical "is the suite green?"
# gate.
#
# USAGE
#   scripts/run-tests.sh                # run every tests/test_*.py, isolated
#   scripts/run-tests.sh -k owner_scope # pass extra args through to pytest
#   PYTEST=./venv/bin/pytest scripts/run-tests.sh
set -u

cd "$(dirname "$0")/.." || exit 2

PY="${PYTHON:-./venv/bin/python}"
[ -x "$PY" ] || PY="python3"

pass=0 fail=0 failed_files=()
start=$SECONDS

for f in tests/test_*.py; do
  # -p no:cacheprovider keeps runs hermetic; -q for terse per-file output.
  if "$PY" -m pytest "$f" -q -p no:cacheprovider "$@" >/tmp/_rt_out 2>&1; then
    pass=$((pass+1))
  else
    fail=$((fail+1)); failed_files+=("$f")
    echo "FAIL  $f"
    tail -n 3 /tmp/_rt_out | sed 's/^/      /'
  fi
done

echo "------------------------------------------------------------"
echo "files: $((pass+fail))  passed: $pass  failed: $fail  (${SECONDS}s)"
if [ "$fail" -ne 0 ]; then
  echo "failed files:"; printf '  %s\n' "${failed_files[@]}"
  exit 1
fi
echo "GREEN — all test files pass in isolation."
