<!--
Copyright (c) Meta Platforms, Inc. and affiliates.
All rights reserved.
-->
# Meta GPU Cluster Monitoring (GCM)

<p align="center">
    <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/logo/Logo_White_BG_Transparent.svg">
    <source media="(prefers-color-scheme: light)" srcset="./assets/logo/Logo_Black_BG_Transparent.svg">
    <img alt="GCM Logo" src="./assets/logo/Logo_Black_BG_Transparent.svg" style="height: 150px;">
    </picture>
</p>

GCM is a set of tools used to do at-scale monitoring for HPC (High-Performance Computing) clusters, it powers [Meta FAIR (Fundamental AI Research)](https://ai.meta.com/research/) AI workloads across hundreds of thousands of GPUs at Meta.

GCM is a monorepo with the following components:

- [Monitoring](gcm/monitoring/): Collects cluster statistics from the [Slurm](https://slurm.schedmd.com/documentation.html) workload scheduler, providing visibility into job performance and resource utilization.
- [Health Checks](gcm/health_checks/): Verifies the proper functioning of hardware, software, network, storage, and services throughout the job lifecycle.
- [Telemetry Processor / GPU Metrics](gcm/slurmprocessor/): Enhances OpenTelemetry data by correlating telemetry with Slurm metadata, enabling attribution of metrics (e.g., GPU utilization) to specific jobs and users.

For more information, check our [documentation](https://facebookresearch.github.io/gcm/).

## Contributing

Each component has its own README with detailed guides:

- [Monitoring](gcm/README.md)
- [Health Checks](gcm/README.md)
- [slurmprocessor](slurmprocessor/README.md)
- [shelper](shelper/README.md)

## Possible Expansions

- Integration with more GPU types (AMD, Intel, Custom Accelerators)
- Support for additional schedulers beyond Slurm
- [Additional Slurm related Monitoring](gcm/docs/monitoring_onboarding.md#monitoring-something-new-with-gcm)
- [Support for new exporters](gcm/docs/monitoring_onboarding.md#adding-a-new-exporter-to-gcm)
- Adding support for [Slurm REST API](https://slurm.schedmd.com/rest_api.html) querying
- Adding support for new [Health Checks](gcm/docs/health_checks_onboarding.md#how-to-write-a-new-health-check?)
- Distribution via Docker Images and Helm Charts

## [Code of Conduct](https://code.fb.com/codeofconduct)

Facebook has adopted a Code of Conduct that we expect project participants to adhere to. Please read [the full text](https://code.fb.com/codeofconduct) so that you can understand what actions will and will not be tolerated.

## The Team

GPU Cluster Monitoring is actively maintained by [Lucca Bertoncini](https://github.com/luccabb), [Caleb Ho](https://github.com/calebho), [Apostolos Kokolis](https://github.com/A-Kokolis), [Liao Hu](https://github.com/L1A0), [Thanh Nguyen](https://github.com/giongto35), [Billy Campoli](https://github.com/tooji) with a number of contributions coming from talented individuals (in no particular order, and non-exhaustive): [Jörg Doku](https://github.com/Jorghi12), [Vivian Peng](https://github.com/vzpeng), [Parth Malani](https://github.com/pmmalani), [Kalyan Saladi](https://github.com/skalyan), [Shubho Sengupta](https://github.com/shubho), [Leo Huang](https://github.com/lifeihuang), [Robert Vincent](https://github.com/bvincent-penguin), [Max Wang](https://github.com/mxw), [Sujit Verma](https://github.com/sujitoc), [Teng Li](https://github.com/teng-li), [James Taylor](https://github.com/jamestaylr), [Xiaodong Ma](https://github.com/xman1979), [Chris Henry](https://github.com/chenry3), [Jakob Johnson](https://github.com/jj10306), [Kareem Sakher](https://github.com/kjsakher), [Abinesh Ramakrishnan](https://github.com/ibanesh), [Nabib Ahmed](https://github.com/nahmed3536), [Yong Li](https://github.com/yonglimeta), [Junjie Qian](https://github.com/junjieqian), [David Watson](https://github.com/davidewatson), [Guanyu Wu](https://github.com/kwu-penguin), [Jaromir Latal](https://github.com/jermenkoo), [Samuel Doud](https://github.com/SamuelDoud), [Yidi Wu](https://github.com/ydwu4), [Xinyuan Zhang](https://github.com/xinyuanzzz), [Neha Saxena](https://github.com/nehasaxena210).

Feel free to contribute and add your name!

## License

Each GCM component has its own lincense.

[/gcm](./gcm) is licensed under the [MIT License](./gcm/LICENSE).

[/shelper](./shelper) is licensed under the [MIT License](./shelper/LICENSE).

[/slurmprocessor](./slurmprocessor) is licensed under the [Apache 2.0 License](./slurmprocessor/LICENSE).

Remaining files are licensed under the [MIT License](./LICENSE).
