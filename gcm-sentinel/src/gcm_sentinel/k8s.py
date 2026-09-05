# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Shared Kubernetes client initialization."""

from kubernetes import client, config


def get_core_api() -> client.CoreV1Api:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api()
