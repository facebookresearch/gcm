<!--
Copyright (c) Meta Platforms, Inc. and affiliates.
All rights reserved.
-->
# Shelper - Slurm Helper Library

Shelper is a Go library designed to help with Slurm-related operations,
particularly for GPU management in a cluster environment. It provides tools to
map GPUs to Slurm jobs and retrieve metadata about those jobs.

## Overview

Shelper provides functionality to:

- Map GPUs to Slurm jobs running on a host
- Retrieve metadata about Slurm jobs
- Query Slurm controllers (slurmctld) for job information
- Cache Slurm metadata to avoid excessive queries
- Parse Slurm hostlists and GPU allocations
- Retrieve information about running processes and their associated Slurm jobs

## Features

### GPU to Slurm Mapping

The core functionality of Shelper is to map GPU devices to the Slurm jobs that
are using them. This is done through the `GetGPU2Slurm` function, which can:

- Query the Slurm controller for job information
- Use local process information to determine GPU allocations
- Cache results to improve performance

### Caching

To avoid excessive queries to the Slurm controller, Shelper includes caching
functionality:

- Cache Slurm metadata for a configurable duration
- Save and load cache from the local filesystem
- Automatically refresh cache when it expires

## Usage

## Functions

- `GetGPU2Slurm`: Maps GPUs to Slurm jobs
- `GetJobMetadata`: Retrieves metadata for a specific Slurm job
- `GetJob2Pid`: Gets mapping of Slurm job IDs to PIDs
- `GetGPU2SlurmFromPIDs`: Maps GPUs to Slurm jobs using PID information
- `GetSlurmMetadataCache`: Retrieves cached Slurm metadata
- `SaveSlurmToJSON`: Saves Slurm metadata to a JSON file
- `AttributeGPU2SlurmMetadata`: Populates GPU to Slurm metadata mapping
- `GetHostList`: Extracts host list from job metadata
- `HostnameInList`: Checks if a hostname is in a Slurm host list
- `parseGRES`: Parses GPU indices from GRES (Generic Resource) output

## Requirements

- Access to Slurm commands (`scontrol`, `squeue`)
- Appropriate permissions to read process information

## License

shelper is licensed under the [MIT](./LICENSE) license.
