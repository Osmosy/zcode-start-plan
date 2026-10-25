#!/usr/bin/env bash
# Сборка ZCode CLI с патчами Start Plan. Требует Node 24 (на 22 ломается TUI).
set -euo pipefail

PIN=3c5b227649371507ddc4eb46ac5133afe6db1cab
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-$HOME/zcode}"
NODE="/usr/bin/node"
[ -x "$NODE" ] || NODE="$(command -v node)"

echo "node: $("$NODE" --version) | цель: $TARGET"
rm -rf "$TARGET" && mkdir -p "$TARGET" && cd "$TARGET"
git init -q
git remote add origin https://github.com/zai-org/ZCode
git fetch --depth 1 origin "$PIN"
git checkout -q FETCH_HEAD
git apply "$HERE/patch/0001-start-plan.patch"
git apply "$HERE/patch/0002-device-mid-and-retry.patch"

npx --yes pnpm@10.33.2 install --frozen-lockfile --filter "@zcode/cli..."
npx --yes pnpm@10.33.2 --filter "@zcode/cli..." build

BUNDLE="$TARGET/apps/zcode-cli/packages/cli/dist/zcode.cjs"
[ -f "$BUNDLE" ] || { echo "нет $BUNDLE — сборка неполная" >&2; exit 1; }
echo "готово: $BUNDLE"
"$NODE" "$BUNDLE" --version
