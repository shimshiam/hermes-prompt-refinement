#!/bin/bash
# Run the tests that need a real Hermes checkout, then restore it exactly.
#
#   scripts/test-in-hermes.sh <hermes-checkout> unit    plugin vitest (UI + real composer), Desktop
#                                                       typecheck against the real SDK, Python half test
#   scripts/test-in-hermes.sh <hermes-checkout> e2e     the full e2e (Off, Approval-First, Automatic)
#                                                       with this repo installed as a Git package
#   scripts/test-in-hermes.sh <hermes-checkout> older   on a Desktop WITHOUT the review SDK: the plugin
#                                                       stays inactive and sends go through untouched
#
# The checkout must be clean, have its toolchain on PATH (pnpm, uv; see its
# README), and for e2e/older a current `pnpm --dir apps/desktop run build`.
# `unit` copies this plugin into the checkout as a bundled plugin; e2e/older
# install it the way `hermes plugins install` lands a package. Everything is
# removed on exit.
set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"
HERMES="$(cd "${1:?usage: test-in-hermes.sh <hermes-checkout> unit|e2e|older}" && pwd)"
MODE="${2:-unit}"
DESKTOP="$HERMES/apps/desktop"
TREE_PLUGIN="$DESKTOP/src/plugins/prompt-refinement"
TREE_PY="$HERMES/plugins/prompt-refinement"
TREE_PY_TEST="$HERMES/tests/plugins/test_prompt_refinement_plugin.py"
SPEC_DIR="$DESKTOP/e2e"
STAGE=""

if [ -n "$(git -C "$HERMES" status --porcelain)" ]; then
  echo "test-in-hermes: $HERMES has uncommitted changes; refusing" >&2
  exit 1
fi

for path in "$TREE_PLUGIN" "$TREE_PY"; do
  if [ -e "$path" ]; then
    echo "test-in-hermes: $path already exists (a checkout with Prompt Refinement bundled); use one without it" >&2
    exit 1
  fi
done

restore() {
  rm -rf "$TREE_PLUGIN" "$TREE_PY" "$TREE_PY_TEST" "$SPEC_DIR"/prompt-refinement-package*.spec.ts
  [ -n "$STAGE" ] && rm -rf "$STAGE"
  git -C "$HERMES" checkout -- apps/desktop/e2e/fixtures.ts
  if [ -n "$(git -C "$HERMES" status --porcelain)" ]; then
    echo "test-in-hermes: WARNING, $HERMES is not clean after restore:" >&2
    git -C "$HERMES" status --porcelain >&2
  fi
}
trap restore EXIT

# A package exactly as `hermes plugins install` clones it (no node_modules).
stage_package() {
  STAGE="$(mktemp -d)"
  mkdir -p "$STAGE/package/desktop"
  cp "$REPO/plugin.yaml" "$REPO/__init__.py" "$STAGE/package/"
  cp "$REPO/desktop/plugin.js" "$STAGE/package/desktop/"
  export PROMPT_REFINEMENT_PACKAGE="$STAGE/package"
}

# The e2e fixture has no pre-launch hook; add one for this run only.
patch_fixtures() {
  python3 - "$DESKTOP/e2e/fixtures.ts" <<'EOF'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text()
a = "  extraConfig?: string\n"
b = "  writeEnvFile(sandbox.hermesHome)\n"
assert s.count(a) == 1 and s.count(b) == 1, 'fixtures.ts changed upstream; update test-in-hermes.sh'
s = s.replace(a, a + "  seedHome?: (hermesHome: string) => void\n")
s = s.replace(b, b + "  options.seedHome?.(sandbox.hermesHome)\n")
p.write_text(s)
EOF
}

case "$MODE" in
  unit)
    cp -R "$REPO/src" "$TREE_PLUGIN"
    mkdir -p "$TREE_PY"
    cp "$REPO/plugin.yaml" "$REPO/__init__.py" "$TREE_PY/"
    cp "$REPO/test/python/test_prompt_refinement_plugin.py" "$TREE_PY_TEST"
    status=0
    (cd "$DESKTOP" && pnpm exec vitest run --project ui src/plugins/prompt-refinement) || status=1
    (cd "$DESKTOP" && NODE_OPTIONS=--max-old-space-size=4096 pnpm run typecheck) || status=1
    (cd "$HERMES" && scripts/run_tests.sh tests/plugins/test_prompt_refinement_plugin.py) || status=1
    exit $status
    ;;
  e2e | older)
    stage_package
    patch_fixtures
    spec="$REPO/test/e2e/prompt-refinement.spec.ts"
    [ "$MODE" = older ] && spec="$REPO/test/e2e/older-desktop.spec.ts"
    cp "$spec" "$SPEC_DIR/prompt-refinement-package.spec.ts"
    cd "$DESKTOP" && pnpm exec playwright test e2e/prompt-refinement-package.spec.ts --workers=1 --reporter=list
    ;;
  *)
    echo "usage: test-in-hermes.sh <hermes-checkout> unit|e2e|older" >&2
    exit 2
    ;;
esac
