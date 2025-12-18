#!/usr/bin/env bash
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
# strict mode
set -euo pipefail
IFS=$'\n\t'

set -x  # echo commands

builddir=$1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION_FILE="$SCRIPT_DIR/../version.txt"
read -r VERSION < "$VERSION_FILE"

if [[ ! -d "$builddir" ]]; then
  >&2 echo "$builddir is not a directory"
  exit 1
fi

tarball="gcm_${VERSION}.orig.tar.gz"
prefix="gcm/"
git archive --format tar.gz --prefix "$prefix" HEAD > "${builddir}/${tarball}"
cd "$builddir"
tar xf "$tarball"
cd "$prefix"
pyox=$(which pyoxidizer)
bin=$(dirname "$pyox")
# assume all tools are installed in $bin
debuild --prepend-path "$bin" -b -us -uc
