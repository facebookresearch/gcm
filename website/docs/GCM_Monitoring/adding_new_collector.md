---
sidebar_position: 5
---

# Adding New Collector

GCM should be easily extensible. To monitor something new with GCM, you'll need to:

1. Add a new CLI command.

See `main.add_command` on [gcm.py](https://github.com/facebookresearch/gcm/blob/main/gcm/monitoring/cli/gcm.py)

2. Copy/Paste existing code to get a python struct that your CLI cmd runs.

This step requires you to create a new file under [`monitoring/cli`](https://github.com/facebookresearch/gcm/tree/main/gcm/monitoring/cli). Then define the base structure to get all the benefits of the CLI options that GCM offers, this means copy/pasting most of the `def main` function, see https://github.com/facebookresearch/gcm/blob/main/gcm/monitoring/cli/sacctmgr_qos.py#L144-L212

3. Add a call to `run_data_collection_loop`.

Step 2 already has a call to `run_data_collection_loop`, but you'll have to edit it to ensure the new collection gets the right parameters.

`data_collection_tasks` is the relevant argument, this receives a list of tuples with:
1. a generator of dataclasses.
2. sink types.

Each tuple defines a single collection, so if you're sending multiple tuples it'll do multiple collections sequentially.

A few things to keep in mind as you're implementing a generator of dataclasses (1):
- generator is good for scaling, you're not loading all the data into memory as opposed to an iterator
- create required schemas under [gcm/schemas](https://github.com/facebookresearch/gcm/tree/main/gcm/schemas)

Sink types (2) tells the exporter what type of data you're producing, see [Telemetry types supported by GCM](telemetry_types.md). The convention is that a generator (1) produces only one of the supported types.

You can call the GCM cli and confirm that this step is working:

```shell
$ gcm <your_collection_name> --help
...
$ gcm <your_collection_name> --sink=stdout --once --log-level=DEBUG
...
```

4. Update configuration files/daemons to trigger new collection to run.

Now all you have to do is deploy the service. This may involve config changes, building binaries, creating new daemons / pods /containers.

For FB internal deployment see [here](https://fburl.com/code/bk3w9aum).
