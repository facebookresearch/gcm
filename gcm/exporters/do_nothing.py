# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from gcm.exporters import register
from gcm.monitoring.sink.protocol import SinkAdditionalParams
from gcm.schemas.log import Log


@register("do_nothing")
class DoNothing:
    """Placeholder Sink"""

    def write(
        self,
        data: Log,
        additional_params: SinkAdditionalParams,
    ) -> None:
        pass
