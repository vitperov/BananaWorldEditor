#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Smoke test for bwe_screenshot.py - builds throwaway house and terrain maps
# with bwe_cli, runs the screenshot tool offscreen on each and asserts on exit
# codes, the saved image and the stdout summary line. Self-contained: all maps
# and images land in a temp dir, nothing in the repo is touched.
#
# Usage:  ./tests/smoke_bwe_screenshot.sh
# Exit code 0 = all passed, 1 = at least one failure.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EDITOR_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BWE_CLI="$EDITOR_ROOT/bwe_cli.py"
SHOT="$EDITOR_ROOT/bwe_screenshot.py"

# All python3 invocations run inside the uv project env; uv is the only
# supported environment, so fail fast instead of failing per-assertion.
if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv not found on PATH - install it first (https://docs.astral.sh/uv/)" >&2
  exit 1
fi

# The tool itself must force QT_QPA_PLATFORM=offscreen before any Qt import.
# This machine has no display and no Xvfb, so a tool that fails to force it
# fails here; the suite never sets the variable, only clears it.
unset QT_QPA_PLATFORM

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass=0
fail=0

# --- helpers --------------------------------------------------------------- #

py() { uv run --project "$EDITOR_ROOT" python3 "$@"; }   # python3 from the uv project env (cwd unchanged)

must() {   # map-building step: a failure here is setup, not an assertion target - abort
  py "$BWE_CLI" "$@" >/dev/null 2>&1 || { echo "error: map setup failed: bwe_cli $*" >&2; exit 1; }
}

run_tool() {   # run_tool <stdout-file> <stderr-file> <tool args...>; caller checks the exit code
  local so="$1" se="$2"; shift 2
  py "$SHOT" "$@" >"$so" 2>"$se"
}

nlines() {   # line count, works without a trailing newline
  if [ -f "$1" ]; then awk 'END{print NR+0}' "$1"; else echo 0; fi
}

md5() { md5sum "$1" | cut -d' ' -f1; }

assert_eq() {   # assert_eq <actual> <expected> <msg>
  if [ "$1" = "$2" ]; then pass=$((pass+1)); echo "  PASS  $3  ($1)"
  else fail=$((fail+1)); echo "  FAIL  $3  (got '$1', want '$2')"; fi
}
assert_ge() {   # assert_ge <actual> <min> <msg>
  if [ "$1" -ge "$2" ] 2>/dev/null; then pass=$((pass+1)); echo "  PASS  $3  ($1 >= $2)"
  else fail=$((fail+1)); echo "  FAIL  $3  ($1 < $2)"; fi
}

# --------------------------------------------------------------------------- #
echo "bwe_screenshot smoke test  (workdir: $WORK)"
echo "editor root:      $EDITOR_ROOT"

echo ""
echo "== throwaway maps =="
HOUSE="$WORK/house.json"
must new "$HOUSE" --size 10 8 --base-prefab House
must fill "$HOUSE" --rect "0 0 10 8" --model Floor
must wall-frame "$HOUSE" --rect "0 0 10 8"
must roof-frame "$HOUSE" --rect "0 0 10 8" --z 1
TERRAIN="$WORK/terrain.json"
must new "$TERRAIN" --size 20 12
must fill "$TERRAIN" --rect "0 0 20 12" --model Grass
must border "$TERRAIN" --rect "0 0 20 12" --model Forest --width 2
[ -s "$HOUSE" ] || { echo "error: house map was not created" >&2; exit 1; }
[ -s "$TERRAIN" ] || { echo "error: terrain map was not created" >&2; exit 1; }
HOUSE_MD5=$(md5 "$HOUSE")
TERRAIN_MD5=$(md5 "$TERRAIN")

echo ""
echo "== house tab happy path =="
HO="$WORK/house_shot.jpg"
HS="$WORK/house_stdout.txt"
HE="$WORK/house_stderr.txt"
rc=0; run_tool "$HS" "$HE" "$HOUSE" --tab house --out "$HO" || rc=$?
assert_eq "$rc" "0" "house: tool exits 0"
if [ -s "$HO" ]; then ho=yes; else ho=no; fi
assert_eq "$ho" "yes" "house: image file is non-empty"
assert_eq "$(nlines "$HS")" "1" "house: stdout is exactly one line"
assert_eq "$(grep -cF "$HO" "$HS")" "1" "house: summary line names the output path"
assert_eq "$(grep -c 1400 "$HS")" "1" "house: summary line carries width 1400"
assert_eq "$(grep -c 900 "$HS")" "1" "house: summary line carries height 900"

echo ""
echo "== terrain tab happy path (generator plugins load like the GUI) =="
TO="$WORK/terrain_shot.jpg"
TS="$WORK/terrain_stdout.txt"
TE="$WORK/terrain_stderr.txt"
rc=0; run_tool "$TS" "$TE" "$TERRAIN" --tab terrain --out "$TO" || rc=$?
assert_eq "$rc" "0" "terrain: tool exits 0 (terrain map + generators load)"
if [ -s "$TO" ]; then to=yes; else to=no; fi
assert_eq "$to" "yes" "terrain: image file is non-empty"
assert_eq "$(nlines "$TS")" "1" "terrain: stdout is exactly one line"
assert_eq "$(grep -cF "$TO" "$TS")" "1" "terrain: summary line names the output path"
assert_eq "$(grep -c 1400 "$TS")" "1" "terrain: summary line carries width 1400"
assert_eq "$(grep -c 900 "$TS")" "1" "terrain: summary line carries height 900"

echo ""
echo "== default tab is house (--tab omitted) =="
# The contract makes house the default tab; a tool defaulting to terrain must fail here.
DO="$WORK/default_shot.jpg"
DS="$WORK/default_stdout.txt"; DE="$WORK/default_stderr.txt"
rc=0; run_tool "$DS" "$DE" "$HOUSE" --out "$DO" || rc=$?
assert_eq "$rc" "0" "default --tab: tool exits 0 (house assumed)"
if [ -s "$DO" ]; then d=yes; else d=no; fi
assert_eq "$d" "yes" "default --tab: image file is non-empty"

echo ""
echo "== image is a real decodable 1400x900 capture =="
# Qt emits a wayland hint on stderr even offscreen - read stdout, ignore stderr.
decode_dims() {   # decode_dims <image> -> "w h", empty on failure
  py - "$1" <<'PYEOF' 2>/dev/null
import sys
from PyQt5.QtGui import QGuiApplication, QImage
_ = QGuiApplication(["x", "-platform", "offscreen"])
img = QImage(sys.argv[1])
print(img.width(), img.height()) if not img.isNull() else None
PYEOF
}
dims=$(decode_dims "$HO")
assert_eq "$dims" "1400 900" "house: saved image decodes at 1400x900"
dims=$(decode_dims "$TO")
assert_eq "$dims" "1400 900" "terrain: saved image decodes at 1400x900"

# QImage sniffs the format from the bytes, so a PNG saved as .jpg would still
# decode above - pin the JPEG magic too (a .jpg output must be JPEG bytes).
jpeg_magic() {   # first 3 bytes as hex, empty if the file is unreadable
  if [ -f "$1" ]; then head -c 3 "$1" | od -An -tx1 | tr -d ' \n'; fi
}
assert_eq "$(jpeg_magic "$HO")" "ffd8ff" "house: .jpg output is real JPEG (magic bytes)"
assert_eq "$(jpeg_magic "$TO")" "ffd8ff" "terrain: .jpg output is real JPEG (magic bytes)"

echo ""
echo "== error paths =="
# map file missing: nothing written, message on stderr
MISSING_OUT="$WORK/missing.jpg"
MS="$WORK/missing_stdout.txt"; ME="$WORK/missing_stderr.txt"
rc=0; run_tool "$MS" "$ME" "$WORK/nope.json" --out "$MISSING_OUT" || rc=$?
if [ "$rc" -ne 0 ]; then nz=yes; else nz=no; fi
assert_eq "$nz" "yes" "missing map: exits non-zero"
if [ -e "$MISSING_OUT" ]; then w=yes; else w=no; fi
assert_eq "$w" "no" "missing map: nothing written at --out"
if [ -s "$ME" ]; then m=yes; else m=no; fi
assert_eq "$m" "yes" "missing map: message on stderr"

# map fails to load (malformed JSON)
BROKEN="$WORK/broken.json"
printf '{ not json' > "$BROKEN"
BS="$WORK/broken_stdout.txt"; BE="$WORK/broken_stderr.txt"
rc=0; run_tool "$BS" "$BE" "$BROKEN" --out "$WORK/broken.jpg" || rc=$?
if [ "$rc" -ne 0 ]; then nz=yes; else nz=no; fi
assert_eq "$nz" "yes" "unloadable map: exits non-zero"
if [ -s "$BE" ]; then m=yes; else m=no; fi
assert_eq "$m" "yes" "unloadable map: message on stderr"

# --out in a nonexistent directory (unwritable)
US="$WORK/unwritable_stdout.txt"; UE="$WORK/unwritable_stderr.txt"
rc=0; run_tool "$US" "$UE" "$HOUSE" --out "$WORK/nodir/x.jpg" || rc=$?
if [ "$rc" -ne 0 ]; then nz=yes; else nz=no; fi
assert_eq "$nz" "yes" "unwritable --out: exits non-zero"
if [ -s "$UE" ]; then m=yes; else m=no; fi
assert_eq "$m" "yes" "unwritable --out: save failure reported on stderr"

# unsupported extension
XY="$WORK/shot.xyz"
XS="$WORK/xyz_stdout.txt"; XE="$WORK/xyz_stderr.txt"
rc=0; run_tool "$XS" "$XE" "$HOUSE" --out "$XY" || rc=$?
if [ "$rc" -ne 0 ]; then nz=yes; else nz=no; fi
assert_eq "$nz" "yes" "unsupported extension: exits non-zero"
if [ -s "$XE" ]; then m=yes; else m=no; fi
assert_eq "$m" "yes" "unsupported extension: failure reported on stderr"
if [ -e "$XY" ]; then w=yes; else w=no; fi
assert_eq "$w" "no" "unsupported extension: nothing written"

# unknown tab value (argparse error)
KT="$WORK/kitchen_stdout.txt"; KE="$WORK/kitchen_stderr.txt"
rc=0; run_tool "$KT" "$KE" "$HOUSE" --tab kitchen --out "$WORK/kitchen.jpg" || rc=$?
if [ "$rc" -ne 0 ]; then nz=yes; else nz=no; fi
assert_eq "$nz" "yes" "unknown tab: exits non-zero"

echo ""
echo "== boundaries =="
assert_eq "$(md5 "$HOUSE")" "$HOUSE_MD5" "house map: byte-identical after all tool runs"
assert_eq "$(md5 "$TERRAIN")" "$TERRAIN_MD5" "terrain map: byte-identical after all tool runs"

# works from any cwd: relative map argument resolves against the invocation cwd
rc=0; (cd "$WORK" && py "$SHOT" house.json --tab house --out "$WORK/cwd_shot.jpg") >/dev/null 2>&1 || rc=$?
assert_eq "$rc" "0" "any cwd: relative map resolves against invocation cwd"
if [ -s "$WORK/cwd_shot.jpg" ]; then c=yes; else c=no; fi
assert_eq "$c" "yes" "any cwd: image written"

# works through the Unity symlink: editor root resolved via realpath
ln -s "$EDITOR_ROOT" "$WORK/bwe_link"
LO="$WORK/link_shot.jpg"
LS="$WORK/link_stdout.txt"; LE="$WORK/link_stderr.txt"
rc=0; py "$WORK/bwe_link/bwe_screenshot.py" "$HOUSE" --tab house --out "$LO" >"$LS" 2>"$LE" || rc=$?
assert_eq "$rc" "0" "symlink: tool exits 0 via symlinked editor root"
if [ -s "$LO" ]; then l=yes; else l=no; fi
assert_eq "$l" "yes" "symlink: image written (root resolved through realpath)"

# a placed object whose icon png is absent must not be an error - its cell is
# left blank (GUI parity); landLot is the one catalog entry without a png
ICONLESS="$WORK/iconless.json"
must new "$ICONLESS" --size 4 4
must place "$ICONLESS" --at 1 1 --model landLot
IO="$WORK/iconless_shot.jpg"
rc=0; py "$SHOT" "$ICONLESS" --tab terrain --out "$IO" >/dev/null 2>&1 || rc=$?
assert_eq "$rc" "0" "missing icon png: tool exits 0 (cell left blank)"
if [ -s "$IO" ]; then i=yes; else i=no; fi
assert_eq "$i" "yes" "missing icon png: image written"

echo ""
echo "=========================================="
echo "  PASSED: $pass    FAILED: $fail"
echo "=========================================="
[ "$fail" -eq 0 ]

