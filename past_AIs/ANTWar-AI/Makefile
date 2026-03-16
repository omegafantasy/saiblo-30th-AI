# Compiler
CXX = g++
# Compiler flags
CXXFLAGS := -std=c++17 -O3

# Include directories
INCLUDEDIRS := .
# Include files
INCLUDES := $(wildcard *.hpp)

# Source directories
SOURCEDIRS := example
# Source files
SOURCES := $(wildcard $(patsubst %, %/*.cpp, $(SOURCEDIRS)))

# Target files
TARGETS := main


all: $(TARGETS)

$(TARGETS): %: %.cpp $(INCLUDES)
	$(CXX) $(CXXFLAGS) -I$(INCLUDEDIRS) -o $@ $<

.PHONY: clean
clean:
	rm -f $(TARGETS)
