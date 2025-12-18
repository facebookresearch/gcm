# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

from typing import Mapping

from pydantic import BaseModel


class Config(BaseModel):
    """Various runtime values to be used in testing. Use sparingly.

    DO NOT use this for clowny things like flags which expose whether the code is
    running inside of a test. Test behavior should match production behavior as much as
    possible.
    """

    # Graph API app token (app_id|ap_secret) for end-to-end testing
    graph_api_access_token: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> Config:
        """Construct from environment variables.

        The convention is that all config values are prefixed with 'GCM_TEST_' and
        converted to uppercase, e.g. a config value 'foo' could be set with value 'bar'
        via the environment with 'GCM_TEST_FOO=bar'.
        """
        kwargs = {}
        for f in cls.model_fields:
            kwargs[f] = environ[f"GCM_TEST_{f.upper()}"]
        return cls(**kwargs)
