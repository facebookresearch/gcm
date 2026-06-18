# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
SHELL:=/bin/bash -o pipefail -o errexit -o nounset

PYOX_DEBUG_OUT=build/x86_64-unknown-linux-gnu/debug
PYOX_RELEASE_OUT=build/x86_64-unknown-linux-gnu/release
GCM_SRCS:=$(shell find gcm/ -type f -name '*py')
VERSION:=$(shell cat gcm/version.txt)
PYOXIDIZER_EXTRA_ARGS:=
ifneq ($(PYOXIDIZER_SYSTEM_RUST),)
PYOXIDIZER_EXTRA_ARGS += --system-rust
endif
ifneq ($(PYOXIDIZER_PYTHON_DISTRIBUTION),)
PYOXIDIZER_EXTRA_ARGS += --var PYTHON_DISTRIBUTION $(PYOXIDIZER_PYTHON_DISTRIBUTION)
endif

.PHONY: all
all: gcm, health_checks

.PHONY: clean
clean: clean_pyox

.PHONY: gcm
gcm: $(PYOX_DEBUG_OUT)/install/gcm

$(PYOX_RELEASE_OUT)/install/gcm: pyoxidizer.bzl requirements.txt $(GCM_SRCS)
	pyoxidizer build --release --var VERSION $(VERSION) $(PYOXIDIZER_EXTRA_ARGS) gcm resources_gcm install_gcm

.PHONY: release/gcm
release/gcm: $(PYOX_RELEASE_OUT)/install/gcm

.PHONY: health_checks
health_checks: $(PYOX_DEBUG_OUT)/install/health_checks

$(PYOX_RELEASE_OUT)/install/health_checks: pyoxidizer.bzl requirements.txt $(GCM_SRCS)
	pyoxidizer build --release --var VERSION $(VERSION) $(PYOXIDIZER_EXTRA_ARGS) health_checks resources_hc install_hc

.PHONY: release/health_checks
release/health_checks: $(PYOX_RELEASE_OUT)/install/health_checks

.PHONY: clean_pyox
clean_pyox:
	rm -rf $(PYOX_DEBUG_OUT) $(PYOX_RELEASE_OUT)

requirements.txt: pyproject.toml
	pip-compile --no-emit-options --generate-hashes --no-reuse-hashes --allow-unsafe --resolver=backtracking -o requirements.txt pyproject.toml

dev-requirements.txt: pyproject.toml
	pip-compile --no-emit-options --generate-hashes --no-reuse-hashes --allow-unsafe --resolver=backtracking --extra dev -o dev-requirements.txt pyproject.toml
