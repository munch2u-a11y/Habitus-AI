CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17
LLAMA_CPP_SOURCE ?= /tmp/llama.cpp-b9509
OLLAMA_LIB_DIR ?= /usr/local/lib/ollama

INCLUDES = -I$(LLAMA_CPP_SOURCE)/include -I$(LLAMA_CPP_SOURCE)/ggml/include
LIBS = -L$(OLLAMA_LIB_DIR) -Wl,-rpath,$(OLLAMA_LIB_DIR) \
	-lllama -lggml -lggml-base -ldl -pthread

.PHONY: all clean

all: graph_soft_generator lexeme_codec

graph_soft_generator: graph_soft_generator.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) $< $(LIBS) -o $@

lexeme_codec: lexeme_codec.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) $< $(LIBS) -o $@

clean:
	rm -f graph_soft_generator lexeme_codec
