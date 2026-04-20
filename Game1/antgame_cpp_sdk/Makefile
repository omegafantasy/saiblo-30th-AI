CXX ?= g++
CXXFLAGS ?= -std=c++17 -O3 -DNDEBUG -Wall -Wextra -Iinclude -I../Ant-Game/game/include
DEPFLAGS := -MMD -MP
AR ?= ar

BUILD_DIR := build
LIB := $(BUILD_DIR)/libantgame_cpp_sdk.a
SDK_HEADERS := $(wildcard include/antgame_sdk/*.hpp)
GAME_SOURCES := $(filter-out ../Ant-Game/game/src/main.cpp,$(wildcard ../Ant-Game/game/src/*.cpp))
GAME_OBJECTS := $(patsubst ../Ant-Game/game/src/%.cpp,$(BUILD_DIR)/game/%.o,$(GAME_SOURCES))
SDK_OBJECTS := $(BUILD_DIR)/native_sim.o
DEPS := $(GAME_OBJECTS:.o=.d) $(SDK_OBJECTS:.o=.d)
LIB_OBJECTS := $(GAME_OBJECTS) $(SDK_OBJECTS)

EXAMPLE_BIN := $(BUILD_DIR)/sdk_example_ai
SMOKE_BIN := $(BUILD_DIR)/sdk_smoke
JSON_RUNNER_BIN := $(BUILD_DIR)/sdk_json_runner
RANDOM_SEARCH_BENCH_BIN := $(BUILD_DIR)/sdk_random_search_bench
ROLLOUT_PROBE_BIN := $(BUILD_DIR)/sdk_rollout_probe

.PHONY: all clean smoke

all: $(LIB) $(EXAMPLE_BIN) $(SMOKE_BIN) $(JSON_RUNNER_BIN) $(RANDOM_SEARCH_BENCH_BIN) $(ROLLOUT_PROBE_BIN)

$(BUILD_DIR)/game/%.o: ../Ant-Game/game/src/%.cpp
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $(DEPFLAGS) -c $< -o $@

$(BUILD_DIR)/native_sim.o: src/native_sim.cpp include/antgame_sdk/sdk.hpp include/antgame_sdk/native_sim.hpp
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $(DEPFLAGS) -c $< -o $@

$(LIB): $(LIB_OBJECTS)
	@mkdir -p $(dir $@)
	$(AR) rcs $@ $^

$(EXAMPLE_BIN): examples/sdk_example_ai.cpp $(SDK_HEADERS) $(LIB)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $< $(LIB) -o $@

$(SMOKE_BIN): examples/sdk_smoke.cpp $(SDK_HEADERS) $(LIB)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $< $(LIB) -o $@

$(JSON_RUNNER_BIN): examples/sdk_json_runner.cpp $(SDK_HEADERS) $(LIB)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $< $(LIB) -o $@

$(RANDOM_SEARCH_BENCH_BIN): examples/sdk_random_search_bench.cpp $(SDK_HEADERS) $(LIB)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $< $(LIB) -o $@

$(ROLLOUT_PROBE_BIN): examples/sdk_rollout_probe.cpp $(SDK_HEADERS) $(LIB)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $< $(LIB) -o $@

smoke: $(SMOKE_BIN)
	./$(SMOKE_BIN)

clean:
	rm -rf $(BUILD_DIR)

-include $(DEPS)
