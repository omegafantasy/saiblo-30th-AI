#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 <cpp_lure_v3n> [output_zip]" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAME1_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET="$1"
OUTPUT_ARG="${2:-}"

case "$TARGET" in
  cpp_lure_v3n)
    SOURCE_MAIN="${SCRIPT_DIR}/cpp_lure_v3n/ai_cpp_lure_v3n.cpp"
    ARCHIVE_NAME="ai_cpp_lure_v3n_cppzip.zip"
    ;;
  *)
    echo "unknown target: ${TARGET}" >&2
    exit 1
    ;;
esac

if [[ ! -f "$SOURCE_MAIN" ]]; then
  echo "source main not found: ${SOURCE_MAIN}" >&2
  exit 1
fi

OUTPUT_ZIP="${OUTPUT_ARG:-${SCRIPT_DIR}/${ARCHIVE_NAME}}"
OUTPUT_PARENT="$(dirname "$OUTPUT_ZIP")"
mkdir -p "$OUTPUT_PARENT"
OUTPUT_ZIP="$(cd "$OUTPUT_PARENT" && pwd)/$(basename "$OUTPUT_ZIP")"

STAGING_DIR="$(mktemp -d "${TMPDIR:-/tmp}/agent-tradition-${TARGET}-cppzip.XXXXXX")"
trap 'rm -rf "$STAGING_DIR"' EXIT

mkdir -p \
  "$STAGING_DIR/antgame_ai" \
  "$STAGING_DIR/antgame_sdk" \
  "$STAGING_DIR/antgame_sdk/src" \
  "$STAGING_DIR/Ant-Game/game/include" \
  "$STAGING_DIR/Ant-Game/game/src"

cp "$SOURCE_MAIN" "$STAGING_DIR/main.cpp"
cp -R "${SCRIPT_DIR}/cpp_lure_v3/include/antgame_ai/." "$STAGING_DIR/antgame_ai/"
cp -R "${GAME1_ROOT}/antgame_cpp_sdk/include/antgame_sdk/." "$STAGING_DIR/antgame_sdk/"
cp "${GAME1_ROOT}/antgame_cpp_sdk/src/native_sim.cpp" "$STAGING_DIR/antgame_sdk/src/native_sim.cpp"
cp -R "${GAME1_ROOT}/Ant-Game/game/include/." "$STAGING_DIR/Ant-Game/game/include/"
find "${GAME1_ROOT}/Ant-Game/game/src" -maxdepth 1 -type f -name '*.cpp' ! -name 'main.cpp' -exec cp {} "$STAGING_DIR/Ant-Game/game/src/" \;

# Saiblo's cpp_zip compiler invokes g++ over the unpacked sources without adding
# the archive root as an include directory. Keep root-level includes in main.cpp,
# but make package-internal includes relative to the including file.
find "$STAGING_DIR/antgame_ai" -type f -name '*.hpp' -exec perl -0pi -e \
  's/#include "antgame_ai\/([^"]+)"/#include "$1"/g; s/#include "antgame_sdk\/([^"]+)"/#include "..\/antgame_sdk\/$1"/g' {} +
find "$STAGING_DIR/antgame_sdk" -maxdepth 1 -type f -name '*.hpp' -exec perl -0pi -e \
  's/#include "antgame_sdk\/([^"]+)"/#include "$1"/g' {} +
perl -0pi -e 's/#include "antgame_sdk\/native_sim\.hpp"/#include "..\/native_sim.hpp"/g' \
  "$STAGING_DIR/antgame_sdk/src/native_sim.cpp"

cat >"$STAGING_DIR/Makefile" <<'MAKEFILE'
CXX ?= g++
CXXFLAGS ?= -std=c++17 -O3 -DNDEBUG -Wall -Wextra -I. -IAnt-Game/game/include
GAME_SOURCES := $(wildcard Ant-Game/game/src/*.cpp)
SOURCES := main.cpp antgame_sdk/src/native_sim.cpp $(GAME_SOURCES)

.PHONY: all clean

all: main

main: $(SOURCES)
	$(CXX) $(CXXFLAGS) $(SOURCES) -o main

clean:
	rm -f main
MAKEFILE

cat >"$STAGING_DIR/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.10)
project(antgame_v3n_perf LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -DNDEBUG -Wall -Wextra")
file(GLOB GAME_SOURCES "Ant-Game/game/src/*.cpp")
add_executable(main main.cpp antgame_sdk/src/native_sim.cpp ${GAME_SOURCES})
target_include_directories(main PRIVATE . Ant-Game/game/include)
CMAKE

rm -f "$OUTPUT_ZIP"
(
  cd "$STAGING_DIR"
  zip -qr "$OUTPUT_ZIP" .
)

printf '%s\n' "$OUTPUT_ZIP"
