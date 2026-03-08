---
sidebar_position: 6
---

# Adding New Exporter

GCM supports multiple [exporters](https://github.com/facebookresearch/gcm/tree/main/gcm/exporters), each one is responsible for exporting data to a different destination. To add a new exporter, you'll need to:

1. Create a file for the new exporter on the [exporters](https://github.com/facebookresearch/gcm/tree/main/gcm/exporters) folder.

See existing [exporters](https://github.com/facebookresearch/gcm/tree/main/gcm/exporters) and choose an appropriate name for the new exporter.

2. Create the exporter class.

Some important things when creating a new exporter class:

1. `@register("<your_exporter_name>")` decorator.

This decorator is used to register the exporter with GCM, so you should be able to call it from the CLI with the `--sink` option:

```
gcm ... --sink=<your_exporter_name> ...
```

2. Arguments to `__init__` method.

If you want to send exporter specific arguments at CLI invocation time (or provide them via config files), you can add them to the `__init__` method. For example, if you want to send a `port` argument to the exporter, you can add it to the `__init__` method like this:

```
def __init__(self, *, port: Optional[int] = None) -> None:
    ...
```

Then you'll be able to call the CLI and send a `port`:

```
gcm ... --sink=<your_exporter_name> -o port=9000 ...
```

3. Implement the `write` method.

This method is responsible for exporting the data to the destination. It receives a [`Log`](https://github.com/facebookresearch/gcm/blob/main/gcm/schemas/log.py) object and a [`SinkAdditionalParams`](https://github.com/facebookresearch/gcm/blob/main/gcm/monitoring/sink/protocol.py) object.

`Log` contains the data to be exported as an iterator of dataclasses.

`SinkAdditionalParams` has a `data_type` field that tells the exporter if it should treat the data as a [LOG](https://github.com/facebookresearch/gcm/blob/main/gcm/monitoring/sink/protocol.py) or [METRIC](https://github.com/facebookresearch/gcm/blob/main/gcm/monitoring/sink/protocol.py), see [Telemetry types supported by GCM](telemetry_types.md):

- This is defined at collection time
- These are commonly used to treat data differently at export time, if needed

To see a real implementation of a simple exporter class and its write method, you can see the stdout exporter [here](https://github.com/facebookresearch/gcm/blob/main/gcm/exporters/stdout.py).

4. Implement the `shutdown` method.

This method is called when GCM is done writing and needs to clean up. It should flush any buffered data and release resources (connections, file handles, etc.). For simple exporters with no resources to release, an empty implementation is fine:

```python
def shutdown(self) -> None:
    pass
```

After you've completed this step, you should be able to test calling your new exporter from the CLI:

```
gcm ... --sink=<your_exporter_name> ... # add the following for any required exporter args: -o key=value
```
