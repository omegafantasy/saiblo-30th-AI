CXX ?= g++
CXXFLAGS ?= -std=c++20 -O2 -pipe -Wall -Wextra -pedantic

all: exact_move_kernel

exact_move_kernel: exact_move_kernel.cpp
	$(CXX) $(CXXFLAGS) exact_move_kernel.cpp -o exact_move_kernel

clean:
	rm -f exact_move_kernel
