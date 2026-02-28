# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from gcm.exporters import register
from gcm.monitoring.sink.protocol import SinkAdditionalParams
from gcm.schemas.log import Log


@register("do_nothing")
class DoNothing:
    """Placeholder Sink"""

    def __init__(self, **kwargs: object) -> None:
        """Initialize DoNothing sink.

        Explicit __init__ is required for compatibility with certain versions
        of typeguard's typechecked() decorator used in monitor.py line 110.

        Args:
            **kwargs: Accepts any keyword arguments to be compatible with
                      sink_kwargs passed from monitor.py line 117. Currently
                      ignores all parameters as DoNothing doesn't need configuration.
        """
        pass

    def write(
        self,
        data: Log,
        additional_params: SinkAdditionalParams,
    ) -> None:
        pass
