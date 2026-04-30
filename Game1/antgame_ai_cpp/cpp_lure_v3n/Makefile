CXX ?= g++
CXXFLAGS ?= -std=c++17 -O3 -DNDEBUG -Wall -Wextra -I../cpp_lure_v3/include -I../../antgame_cpp_sdk/include -I../../Ant-Game/game/include

BUILD_DIR := build
CPP_SDK_DIR := ../../antgame_cpp_sdk
V3_DIR := ../cpp_lure_v3
LIB := $(CPP_SDK_DIR)/build/libantgame_cpp_sdk.a
SDK_HEADERS := $(wildcard $(CPP_SDK_DIR)/include/antgame_sdk/*.hpp)
V3_HEADERS := $(wildcard $(V3_DIR)/include/antgame_ai/*.hpp)
BIN := $(BUILD_DIR)/ai_cpp_lure_v3n

.PHONY: all clean

all: $(BIN)

$(BIN): ai_cpp_lure_v3n.cpp $(V3_HEADERS) $(SDK_HEADERS) $(LIB)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $< $(LIB) -o $@

$(LIB):
	$(MAKE) -C $(CPP_SDK_DIR) -j2 build/libantgame_cpp_sdk.a

clean:
	rm -rf $(BUILD_DIR)
