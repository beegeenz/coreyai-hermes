#!/bin/sh
# =============================================================================
# check-model.sh — validate the (model.provider, model.default) pair
# =============================================================================
# Catches the class of mistake that took Hermes down on 2026-10-19:
#
#   model:
#     provider: "deepseek"      # <- concrete provider
#     default:  "strata"        # <- an ALIAS NAME, not a model id
#
# That sends the literal string "strata" to api.deepseek.com, which answers
#   HTTP 400: The supported API model names are deepseek-flash, deepseek-v4-pro,
#             but you passed strata.
# and, being a BadRequestError, it is NOT retried — every turn fails.
#
# Usage:
#   tools/check-model.sh              # auto-detect config.yaml
#   tools/check-model.sh FILE         # explicit file
#   HERMES_CONFIG=FILE tools/check-model.sh
#
# Exit: 0 = consistent, 1 = broken pair, 2 = could not read config.
# =============================================================================
set -u

# --- locate config ----------------------------------------------------------
CFG="${1:-${HERMES_CONFIG:-}}"
if [ -z "$CFG" ]; then
    if [ -f /opt/data/config.yaml ]; then
        CFG=/opt/data/config.yaml          # inside the Hermes container
    elif [ -f "$HOME/.hermes/config.yaml" ]; then
        CFG="$HOME/.hermes/config.yaml"
    else
        echo "check-model: no config.yaml found" >&2
        exit 2
    fi
fi
[ -r "$CFG" ] || { echo "check-model: cannot read $CFG" >&2; exit 2; }

# --- helpers ----------------------------------------------------------------
# Print a top-level YAML block: from "^name:" to the next unindented line.
block() {
    sed -n "/^$1:/,/^[^[:space:]#]/p" "$CFG"
}
# Strip surrounding quotes and trailing whitespace.
unquote() {
    tr -d '"' | sed 's/[[:space:]]*$//'
}

model_block=$(block model)
provider=$(printf '%s\n' "$model_block" | sed -n 's/^  provider:[[:space:]]*//p' | unquote | head -1)
model_id=$(printf '%s\n' "$model_block" | sed -n 's/^  default:[[:space:]]*//p' | unquote | head -1)
[ -n "$model_id" ] || model_id=$(printf '%s\n' "$model_block" | sed -n 's/^  model:[[:space:]]*//p' | unquote | head -1)

alias_names=$(block model_aliases | sed -n 's/^  \([A-Za-z0-9_-][A-Za-z0-9_-]*\):[[:space:]]*$/\1/p')
provider_names=$(block providers | sed -n 's/^  \([A-Za-z0-9_-][A-Za-z0-9_-]*\):[[:space:]]*$/\1/p')

fail=0
echo "config:   $CFG"
echo "provider: ${provider:-<unset>}"
echo "model:    ${model_id:-<unset>}"

# --- 1. the exact failure mode: a bare alias used as a model id -------------
if [ -n "$model_id" ]; then
    for a in $alias_names; do
        if [ "$a" = "$model_id" ]; then
            echo
            echo "FAIL: model.default is the ALIAS NAME '$a', not a model id." >&2
            echo "      Hermes will request a model literally called '$a' from" >&2
            echo "      provider '${provider:-?}', which does not exist -> HTTP 400," >&2
            echo "      and 400s are not retried, so every turn fails." >&2
            echo "      Fix: set model.provider to the alias's provider and" >&2
            echo "           model.default to the alias's model, e.g." >&2
            echo "             hermes config set model.provider strata" >&2
            echo "             hermes config set model.default qwen3.8-flash-next" >&2
            fail=1
        fi
    done
fi

# --- 2. known provider/model pair checks ------------------------------------
case "$provider" in
    deepseek)
        # Verified against the API's own 400 message.
        case "$model_id" in
            deepseek-flash|deepseek-v4-pro) : ;;
            *)
                echo
                echo "FAIL: provider 'deepseek' does not serve model '$model_id'." >&2
                echo "      Its API accepts only: deepseek-flash, deepseek-v4-pro" >&2
                fail=1
                ;;
        esac
        ;;
    "")
        echo
        echo "FAIL: model.provider is unset; set it explicitly." >&2
        fail=1
        ;;
    *)
        # A named custom provider would be caught here only if it is declared.
        if ! printf '%s\n' "$provider_names" | grep -qx -- "$provider"; then
            echo
            echo "WARN: '$provider' is not declared under providers: — if it is not a" >&2
            echo "      built-in provider, Hermes will reject it at call time." >&2
        fi
        ;;
esac

# --- 3. reachability of a declared custom provider --------------------------
api=$(block providers \
      | awk -v want="$provider" '
            /^  [A-Za-z0-9_-]+:[[:space:]]*$/ { name=$1; sub(/:.*/,"",name); next }
            name==want && /^    (api|base_url):/ { sub(/^    (api|base_url):[[:space:]]*/,""); print; exit }' \
      | unquote)

if [ -n "$api" ]; then
    # Health usually lives at the server root, not under /v1: strip a trailing
    # /v1 first, then fall back to the full path. Any HTTP status means the
    # socket is answering; only 000 is a real reachability failure.
    base=${api%/}
    base=${base%/v1}
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$base/health" 2>/dev/null || echo 000)
    [ "$code" = "000" ] && code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "${api%/}/health" 2>/dev/null || echo 000)
    if [ "$code" = "000" ]; then
        echo
        echo "FAIL: provider '$provider' endpoint $api is not reachable." >&2
        echo "      Start the backend (for Strata: systemctl --user start strata-128k)." >&2
        fail=1
    else
        echo "endpoint: $api (HTTP $code)"
    fi
fi

echo
if [ "$fail" -ne 0 ]; then
    echo "RESULT: FAIL — fix the pair above before relying on the gateway." >&2
    echo "        Then verify with NO flags:  hermes chat -Q -q \"Reply with exactly: OK\"" >&2
    exit 1
fi
echo "RESULT: PASS — provider/model pair is consistent."
exit 0
