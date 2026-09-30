#!/usr/bin/env bash
# Offline syntax check for the ESP32 firmware.
#
# The Arduino toolchain is not required: the Arduino-facing translation units are
# type-checked against the API stubs in tools/stubs. This catches typos, wrong
# argument counts and missing declarations before a board is flashed. It cannot
# verify register-level behaviour, timing on real hardware or pin correctness.
#
# Usage: bash tools/check_firmware.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIRMWARE_DIR="$ROOT/firmware/robot"
STUBS_DIR="$ROOT/tools/stubs"
OUT_DIR="$ROOT/build"
CXX="${CXX:-g++}"

mkdir -p "$OUT_DIR"

echo "==> firmware control logic and JSON writer (native tests)"
"$CXX" -std=c++17 -Wall -Wextra -Werror -I"$FIRMWARE_DIR" \
  "$FIRMWARE_DIR/robot_logic.cpp" "$ROOT/tools/firmware_logic_test.cpp" \
  -o "$OUT_DIR/firmware_logic_test"
"$OUT_DIR/firmware_logic_test"

"$CXX" -std=c++17 -Wall -Wextra -Werror -I"$FIRMWARE_DIR" \
  "$FIRMWARE_DIR/json_writer.cpp" "$ROOT/tools/json_writer_test.cpp" \
  -o "$OUT_DIR/json_writer_test"
"$OUT_DIR/json_writer_test"

echo "==> Arduino-facing sources (syntax check against API stubs)"
for source in sensors.cpp emitter.cpp motors.cpp robot_network.cpp telemetry.cpp; do
  printf '    %s\n' "$source"
  "$CXX" -std=c++17 -Wall -Wextra -Werror -fsyntax-only \
    -DESP32=1 -DARDUINO=10819 \
    -I"$STUBS_DIR" -I"$FIRMWARE_DIR" \
    "$FIRMWARE_DIR/$source"
done

# robot.ino is compiled as C++ by the Arduino builder.
echo "==> robot.ino (compiled as C++, as the Arduino builder does)"
cp "$FIRMWARE_DIR/robot.ino" "$OUT_DIR/robot_syntax_check.cpp"
"$CXX" -std=c++17 -Wall -Wextra -Werror -fsyntax-only \
  -DESP32=1 -DARDUINO=10819 \
  -I"$STUBS_DIR" -I"$FIRMWARE_DIR" \
  "$OUT_DIR/robot_syntax_check.cpp"
rm -f "$OUT_DIR/robot_syntax_check.cpp"

echo "firmware checks passed"
