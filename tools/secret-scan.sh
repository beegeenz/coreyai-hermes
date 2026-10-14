#!/bin/sh
# =============================================================================
# Secret scanner for the ~/.hermes repository.
# =============================================================================
# Run by .git/hooks/pre-commit, and usable standalone:
#
#   sh tools/secret-scan.sh
#
# Checks STAGED content for (a) the live values of every variable in
# ~/.hermes/.env, and (b) anything shaped like a credential. Exits non-zero if
# it finds something, so the commit is refused.
#
# This directory holds real API keys, so a single .gitignore mistake would be
# published permanently in git history. Cheap insurance.
# =============================================================================
set -u

ENV_FILE="${HERMES_ENV_FILE:-$HOME/.hermes/.env}"
fail=0

# Resolve the repo from THIS script's own location, never the caller's cwd.
# The pre-commit hook happens to run from the repo root, but invoking the
# scanner by hand from anywhere else would otherwise diff the WRONG repository
# and silently pass — a false "clean" is worse than no check at all.
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

staged() {
    # --cached diff of the index; binary-safe enough for a text scan
    git -C "$ROOT" diff --cached --no-color --unified=0 2>/dev/null
}

# --- 1. Live secret values read from .env (values are never echoed) ----------
if [ -f "$ENV_FILE" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            ''|\#*) continue ;;
        esac
        key=${line%%=*}
        val=${line#*=}
        # strip surrounding quotes/whitespace
        val=$(printf '%s' "$val" | tr -d "\"'" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        # only interesting if it is long enough to be a real secret
        [ "${#val}" -ge 12 ] || continue
        if staged | grep -qF -- "$val"; then
            echo "✗ secret-scan: the value of \$$key appears in staged content." >&2
            fail=1
        fi
    done < "$ENV_FILE"
else
    echo "… secret-scan: $ENV_FILE not found — skipping live-value check." >&2
fi

# --- 2. Generic credential shapes -------------------------------------------
PATTERNS='sk-[A-Za-z0-9_-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|[0-9a-f]{40,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}'
if staged | grep -nE "$PATTERNS" >/dev/null 2>&1; then
    echo "✗ secret-scan: staged content matches a credential pattern:" >&2
    staged | grep -nE "$PATTERNS" | cut -d: -f1 | sed 's/^/    staged line /' >&2
    fail=1
fi

if [ "$fail" -ne 0 ]; then
    echo "" >&2
    echo "  Commit refused. Move the value into ~/.hermes/.env and reference it" >&2
    echo "  by name (key_env), or add a .gitignore rule." >&2
    echo "  Override only if certain: git commit --no-verify" >&2
    exit 1
fi

exit 0
