CXX ?= g++
CXXFLAGS ?= -std=c++17 -O3 -DNDEBUG -Wall -Wextra -I../../antgame_cpp_sdk/include -I../../Ant-Game/game/include
AR ?= ar

BUILD_DIR := build
CPP_SDK_DIR := ../../antgame_cpp_sdk
LIB := $(CPP_SDK_DIR)/build/libantgame_cpp_sdk.a
SDK_HEADERS := $(wildcard $(CPP_SDK_DIR)/include/antgame_sdk/*.hpp)
BIN := $(BUILD_DIR)/ai_cpp_heavy_baseline

.PHONY: all clean

all: $(BIN)

$(BIN): ai_cpp_heavy_baseline.cpp $(SDK_HEADERS) $(LIB)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $< $(LIB) -o $@

$(LIB):
	$(MAKE) -C $(CPP_SDK_DIR) -j2 build/libantgame_cpp_sdk.a

clean:
	rm -rf $(BUILD_DIR)
