# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
SHELL:=/bin/bash -o pipefail -o errexit -o nounset

# PyInstaller output directories
PYINSTALLER_OUT=dist
GCM_SRCS:=$(shell find gcm/ -type f -name '*py')
VERSION:=$(shell cat gcm/version.txt)

.PHONY: all
all: gcm health_checks

.PHONY: clean
clean: clean_pyinstaller

.PHONY: gcm
gcm: $(PYINSTALLER_OUT)/gcm/gcm

$(PYINSTALLER_OUT)/gcm/gcm: gcm.spec requirements.txt $(GCM_SRCS)
	GCM_VERSION=$(VERSION) pyinstaller gcm.spec --noconfirm

.PHONY: release/gcm
release/gcm: $(PYINSTALLER_OUT)/gcm/gcm

.PHONY: health_checks
health_checks: $(PYINSTALLER_OUT)/health_checks/health_checks

$(PYINSTALLER_OUT)/health_checks/health_checks: health_checks.spec requirements.txt $(GCM_SRCS)
	GCM_VERSION=$(VERSION) pyinstaller health_checks.spec --noconfirm

.PHONY: release/health_checks
release/health_checks: $(PYINSTALLER_OUT)/health_checks/health_checks

.PHONY: clean_pyinstaller
clean_pyinstaller:
	rm -rf $(PYINSTALLER_OUT) build

requirements.txt: pyproject.toml
	pip-compile --no-emit-options --generate-hashes --no-reuse-hashes --allow-unsafe --resolver=backtracking -o requirements.txt pyproject.toml

dev-requirements.txt: pyproject.toml
	pip-compile --no-emit-options --generate-hashes --no-reuse-hashes --allow-unsafe --resolver=backtracking --extra dev -o dev-requirements.txt pyproject.toml
