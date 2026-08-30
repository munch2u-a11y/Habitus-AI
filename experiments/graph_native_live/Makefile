MODEL ?= /home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf
LLAMA_CPP_SOURCE ?= /tmp/llama.cpp-b9509
OLLAMA_LIB_DIR ?= /usr/local/lib/ollama

.PHONY: build live opaque nursery embodied-nursery reverse-nursery gestate-fast transformer-hatch test

build:
	$(MAKE) -C native LLAMA_CPP_SOURCE=$(LLAMA_CPP_SOURCE) OLLAMA_LIB_DIR=$(OLLAMA_LIB_DIR)

live: build
	cd ../.. && PYTHONPATH=src python3 experiments/graph_native_live/live_tester.py --model $(MODEL) --show-trace

opaque: build
	cd ../.. && PYTHONPATH=src python3 experiments/graph_native_live/opaque_skeleton.py --model $(MODEL)

nursery: build
	cd ../.. && PYTHONPATH=src python3 experiments/graph_native_live/nursery.py --model $(MODEL)

embodied-nursery:
	cd ../.. && PYTHONPATH=src python3 experiments/graph_native_live/embodied_nursery.py

reverse-nursery: build
	cd ../.. && PYTHONPATH=src python3 experiments/graph_native_live/reverse_nursery.py --model $(MODEL)

gestate-fast: build
	cd ../.. && PYTHONPATH=src python3 experiments/graph_native_live/accelerated_gestation.py --model $(MODEL)

transformer-hatch: build
	cd ../.. && PYTHONPATH=src python3 experiments/graph_native_live/transformer_hatch.py --model $(MODEL)

test:
	cd ../.. && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_graph_native_live.py tests/test_opaque_graph_native.py tests/test_nursery.py tests/test_embodied_nursery.py tests/test_reverse_nursery.py tests/test_accelerated_gestation.py
