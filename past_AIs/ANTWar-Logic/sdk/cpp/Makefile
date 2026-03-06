# Compiler
CXX = g++
# Compiler flags
CXXFLAGS := -std=c++11 -O2

INCLUDEDIRS := .
INCLUDES := $(wildcard *.hpp)

SOURCEDIRS := example
SOURCES := $(wildcard $(patsubst %, %/*.cpp, $(SOURCEDIRS)))

TARGETS := $(patsubst %.cpp, %, $(SOURCES))

all: $(TARGETS)

$(TARGETS): %: %.cpp $(INCLUDES)
	$(CXX) $(CXXFLAGS) -I$(INCLUDEDIRS) -o $@ $<

.PHONY: clean
clean:
	rm -f $(TARGETS)
