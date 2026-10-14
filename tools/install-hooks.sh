#!/bin/sh
# Install the repo's git hooks. .git/hooks is not versioned, so run this after
# cloning the ~/.hermes repo onto a new machine:
#
#   sh tools/install-hooks.sh
#
set -eu

root=$(git rev-parse --show-toplevel)
hook="$root/.git/hooks/pre-commit"

cat > "$hook" <<'EOF'
#!/bin/sh
# Pre-commit gate for the ~/.hermes repo. Delegates to the committed scanner so
# the logic is versioned rather than living only in .git/hooks (which git does
# not track). Re-install on a fresh clone with: tools/install-hooks.sh
exec "$(git rev-parse --show-toplevel)/tools/secret-scan.sh"
EOF

chmod +x "$hook" "$root/tools/secret-scan.sh"
echo "✓ installed $hook"
