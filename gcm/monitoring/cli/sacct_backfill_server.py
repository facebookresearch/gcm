#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""A rendezvous server for backfilling data from multiple clusters in lockstep.

Hive partitions are not updatable, so you need to overwrite the entire partition when
you want to update the data. This means that when we write data for a given day from one
cluster, we also need to write the data for the same day on the other. The size of the
data is different across clusters; in general, H1 is much smaller than H2 so it has
fewer jobs. In order to prevent H1 from getting ahead of H2, we need to synchronize
the progress using a barrier.
"""
import logging
from functools import lru_cache
from multiprocessing import Barrier
from multiprocessing.managers import BaseManager
from multiprocessing.synchronize import Barrier as TBarrier
from uuid import uuid4

import click
from typeguard import typechecked

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class BarrierManager(BaseManager):
    pass


@click.command(help=__doc__)
@click.option(
    "--port",
    "-p",
    type=int,
    default=50000,
)
@click.option(
    "--nprocs",
    type=int,
)
@typechecked
def main(port: int, nprocs: int) -> None:
    def get_barrier(start: str, end: str) -> TBarrier:
        logger.info(f"Fetching barrier for {start} {end}")
        return get_barrier_impl(start, end)

    @lru_cache(maxsize=None, typed=True)
    def get_barrier_impl(start: str, end: str) -> TBarrier:
        return Barrier(nprocs)

    BarrierManager.register("get_barrier", callable=get_barrier)
    authkey = uuid4()
    m = BarrierManager(address=("", port), authkey=authkey.bytes)
    s = m.get_server()
    print(s.address)
    print(authkey.hex)
    s.serve_forever()


if __name__ == "__main__":
    main()
