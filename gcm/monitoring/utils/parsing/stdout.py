# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import fields, is_dataclass
from logging import Logger
from typing import Iterable, List, Optional, Tuple, Type, TypeVar

_TDataclass = TypeVar("_TDataclass")


def parse_delimited(
    lines: Iterable[str],
    schema: Type[_TDataclass],
    delimiter: Optional[str],
    logger: Logger,
) -> Tuple[List[str], Iterable[List[str]]]:
    """Return the header and data of `delimiter` delimited data.

    The first line is the "header", i.e. the column names. The remaining lines are the
    records.

    Only recognized columns defined by `valid_fieldnames` will appear in the results.

    If a column name appears more than once, the first occurrence is used.

    If the number of fields in a row is fewer than the number of columns, it is
    skipped.
    """
    if not is_dataclass(schema):
        raise TypeError(f"{type(schema).__name__} is not a dataclass.")
    iter_lines = iter(lines)

    # extract header and the indices of the data we need
    if delimiter is not None:
        all_fieldnames = [n.strip() for n in next(iter_lines).split(delimiter)]
    else:
        all_fieldnames = [n.strip() for n in next(iter_lines).split()]
    valid_fieldnames = [f.metadata.get("field_name", f.name) for f in fields(schema)]
    num_fields = len(valid_fieldnames)
    valid_idx = set()
    cnt_job_id = 0
    header = []
    for i, fn in enumerate(all_fieldnames):
        if fn not in valid_fieldnames:
            continue
        if fn == "JOBID":
            # SLURM returns 2 JOBID, the 2nd one is JOBID_RAW which represents a unique jobid
            cnt_job_id = cnt_job_id + 1
            fn = "JOBID_RAW" if cnt_job_id == 2 else "JOBID"

        valid_idx.add(i)
        header.append(fn)
        # SLURM commands are clowny--two different columns can have the
        # name, so default to the first one we see to avoid duplication
        # for STATE we actually want the long form, which is the second
        # appearance of STATE
        # TODO @luccabb: Fix the logic because STATE is returned only once in the latest version of SLURM.
        # The long form and short form of state are StateLong and StateCompact, respectively.
        if fn not in ["STATE", "JOBID", "JOBID_RAW"]:
            valid_fieldnames.remove(fn)

    if len(header) != num_fields:
        logger.warning(
            f"Header length ({len(header)}) != number of fields ({num_fields})"
        )

    def gen_rows() -> Iterable[List[str]]:
        for line in iter_lines:
            if not line:
                continue

            if delimiter is not None:
                data = [x.strip() for x in line.split(delimiter)]
            else:
                data = [x.strip() for x in line.split()]
            row = [datum for i, datum in enumerate(data) if i in valid_idx]
            if len(row) != len(header):
                # This is happening because the COMMENT string is not escaped, causing certain
                # entries to span more than one row. See T53501045. For now, just log the error
                # and continue
                logger.warning(
                    f"Row length ({len(row)}) != header length ({len(header)}). Line: '{line}'"
                )
                continue
            yield row

    return header, gen_rows()
