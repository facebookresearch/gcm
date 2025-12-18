# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os

if "GCM_DEBUG" in os.environ:
    logging.basicConfig(level=logging.DEBUG)
