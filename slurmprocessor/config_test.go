// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package main

import (
	"path"
	"testing"

	"github.com/stretchr/testify/require"
	"go.opentelemetry.io/collector/component"
	"go.opentelemetry.io/collector/exporter"
	"go.opentelemetry.io/collector/otelcol"
	"go.opentelemetry.io/collector/otelcol/otelcoltest"
	"go.opentelemetry.io/collector/processor"
	"go.opentelemetry.io/collector/receiver"
	"go.opentelemetry.io/collector/service/internal/testcomponents"
)

func TestLoadConfig(t *testing.T) {
	factories := otelcol.Factories{
		Receivers: map[component.Type]receiver.Factory{
			component.MustNewType("examplereceiver"): testcomponents.ExampleReceiverFactory,
		},
		Processors: map[component.Type]processor.Factory{
			component.MustNewType("slurm"): NewFactory(),
		},
		Exporters: map[component.Type]exporter.Factory{
			component.MustNewType("exampleexporter"): testcomponents.ExampleExporterFactory,
		},
	}

	cfg, err := otelcoltest.LoadConfigAndValidate(path.Join(".", "testdata", "config.yaml"), factories)
	require.NoError(t, err)
	require.NotNil(t, cfg)
}
