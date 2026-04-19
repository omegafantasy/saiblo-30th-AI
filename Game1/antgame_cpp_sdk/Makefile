CXX ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Iinclude -I../Ant-Game/game/include
AR ?= ar

BUILD_DIR := build
LIB := $(BUILD_DIR)/libantgame_cpp_sdk.a
GAME_SOURCES := $(filter-out ../Ant-Game/game/src/main.cpp,$(wildcard ../Ant-Game/game/src/*.cpp))
GAME_OBJECTS := $(patsubst ../Ant-Game/game/src/%.cpp,$(BUILD_DIR)/game/%.o,$(GAME_SOURCES))
SDK_OBJECTS := $(BUILD_DIR)/native_sim.o
LIB_OBJECTS := $(GAME_OBJECTS) $(SDK_OBJECTS)

EXAMPLE_BIN := $(BUILD_DIR)/sdk_example_ai
SMOKE_BIN := $(BUILD_DIR)/sdk_smoke
JSON_RUNNER_BIN := $(BUILD_DIR)/sdk_json_runner
HEAVY_BASELINE_BENCH_BIN := $(BUILD_DIR)/sdk_heavy_baseline_bench

.PHONY: all clean smoke

all: $(LIB) $(EXAMPLE_BIN) $(SMOKE_BIN) $(JSON_RUNNER_BIN) $(HEAVY_BASELINE_BENCH_BIN)

$(BUILD_DIR)/game/%.o: ../Ant-Game/game/src/%.cpp
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/native_sim.o: src/native_sim.cpp include/antgame_sdk/sdk.hpp include/antgame_sdk/native_sim.hpp
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(LIB): $(LIB_OBJECTS)
	@mkdir -p $(dir $@)
	$(AR) rcs $@ $^

$(EXAMPLE_BIN): examples/sdk_example_ai.cpp $(LIB)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $< $(LIB) -o $@

$(SMOKE_BIN): examples/sdk_smoke.cpp $(LIB)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $< $(LIB) -o $@

$(JSON_RUNNER_BIN): examples/sdk_json_runner.cpp $(LIB)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $< $(LIB) -o $@

$(HEAVY_BASELINE_BENCH_BIN): examples/sdk_heavy_baseline_bench.cpp $(LIB)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $< $(LIB) -o $@

smoke: $(SMOKE_BIN)
	./$(SMOKE_BIN)

clean:
	rm -rf $(BUILD_DIR)
