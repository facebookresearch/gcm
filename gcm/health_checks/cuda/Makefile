# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
CUDA_PATH = "/public/apps/cuda/11.2"
NVCC = $(CUDA_PATH)/bin/nvcc -ccbin gcc
FLAG = -O3 -Wall -Wextra

.PHONY: all
all: build

.PHONY: build
build: cudaMemTest

cudaMemTest: cudaMemTest.c
	$(NVCC) -Xcompiler -O3 -Xcompiler -Wall -Xcompiler -fPIC -Xcompiler -Wextra $< -o $@

.PHONY: clean
clean:
	rm -f cudaMemTest
