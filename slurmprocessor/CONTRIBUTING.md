<!--
Copyright (c) Meta Platforms, Inc. and affiliates.
All rights reserved.
-->
# Contributing to `slurmprocessor`

See slurmprocessor [getting started](./README.md#getting-started) guide.

## Environment Setup

Install Go in your system. See [Go installation guide](https://go.dev/doc/install) for more details.

## Tests
```shell
go test .
```
​​​
## Formatting
To check formatting:
```shell
gofmt -s -l .
```
​​​
## Lint

To check linting you'll need to install `golangci-lint` in your system. See [golangci-lint installation guide](https://golangci-lint.run/usage/install/#local-installation) for more details. If you already have go installed, you can run the following command to install `golangci-lint`:

```shell
go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.2.1
export PATH="$PATH:$(go env GOPATH)/bin"
```

To check linting:

```shell
golangci-lint run
```
​​​
## Updating dependencies
Import your dependency in one of the `.go` files and then run:
```shell
go mod tidy
```
