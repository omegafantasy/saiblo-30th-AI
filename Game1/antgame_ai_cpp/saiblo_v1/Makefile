CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra -Wshadow -Wconversion
TARGET := ai_saiblo_v1
SRC := ai_saiblo_v1.cpp

all: $(TARGET)

$(TARGET): $(SRC)
	$(CXX) $(CXXFLAGS) -o $@ $(SRC)

clean:
	rm -f $(TARGET)
