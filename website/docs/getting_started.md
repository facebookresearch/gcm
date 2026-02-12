---
sidebar_position: 1
---

# Getting Started

## Introduction

GCM is a set of tools used to do at-scale monitoring for HPC (High-Performance Computing) clusters, it powers [Meta FAIR (Fundamental AI Research)](https://ai.meta.com/research/) AI workloads across over hundreds of thousands of GPUs at Meta.

GCM is a monorepo with the following components:

- [GCM Monitoring](./GCM_Monitoring/getting_started.md): Continuous data collection, mostly for the [Slurm](https://slurm.schedmd.com/documentation.html) workload scheduler, providing visibility into job performance and resource utilization.
- [GCM Health Checks](./GCM_Health_Checks/getting_started.md): Verifies the proper functioning of hardware, software, network, storage, and services throughout the job lifecycle.
- [GCM GPU Metrics](./GCM_GPU_Metrics/getting_started.md): Enhances OpenTelemetry data by correlating telemetry with Slurm metadata, enabling attribution of metrics (e.g., GPU utilization) to specific jobs and users.

<img src="/gcm/img/gcm_high_level.png" style={{ maxHeight: '400px', display: 'block', margin: '0 auto' }} />

Each component has their own Getting Started and Contributing Guide:

### Getting Started

- [Monitoring](./GCM_Monitoring/getting_started.md)
- [Health Checks](./GCM_Health_Checks/getting_started.md)
- [Telemetry Processor / GPU Metrics](./GCM_GPU_Metrics/getting_started.md)

### Contributing

- [Monitoring](./GCM_Monitoring/contributing.md)
- [Health Checks](./GCM_Health_Checks/contributing.md)
- [Telemetry Processor / GPU Metrics](./GCM_GPU_Metrics/contributing.md)

## Others

### Community

You can [ask questions](https://github.com/facebookresearch/gcm/discussions), [open issues and feature-requests](https://github.com/facebookresearch/gcm/issues) in [Github](https://github.com/facebookresearch/gcm/).

### Citing GCM
If you use GCM in your research please use the following BibTeX entry:

```
@software{Bertoncini_Meta_GPU_Cluster,
title = {Meta GPU Cluster Monitoring (GCM): Large-Scale AI Research Cluster Monitoring},
author = {Bertoncini, Lucca and Ho, Caleb and Kokolis, Apostolos and Hu, Liao and Nguyen, Thanh and Campoli, Billy and Doku, Jörg and Peng, Vivian and Wang, Max and Verma, Sujit and Li, Teng and Saxena, Neha and Johnson, Jakob and Malani, Parth and Saladi, Kalyan and Sengupta, Shubho},
howpublished = {Github},
year =         {2025},
url = {https://github.com/facebookresearch/gcm/}
}
```
