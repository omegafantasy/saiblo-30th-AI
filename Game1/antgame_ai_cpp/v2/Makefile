CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra -Wshadow -Wconversion
INCLUDES = -I../../Ant-Game/game/include
TARGET = ai_v2
SRC = ai_v2.cpp

all: $(TARGET)

$(TARGET): $(SRC)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -o $@ $(SRC)

clean:
	rm -f $(TARGET)

.PHONY: all clean
