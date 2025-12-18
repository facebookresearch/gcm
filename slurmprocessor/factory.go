// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package main

import (
	"context"
	"log"

	"github.com/open-telemetry/opentelemetry-collector-contrib/processor/attributesprocessor/internal/metadata"
	"go.opentelemetry.io/collector/component"
	"go.opentelemetry.io/collector/consumer"
	"go.opentelemetry.io/collector/processor"
	"go.opentelemetry.io/collector/processor/processorhelper"

	shelper "github.com/fairinternal/fair-cluster-monitoring/shelper"
)

const (
	// The value of "type" key in configuration.
	typeStr = "slurm"
)

// NewFactory creates a factory for the routing processor.
func NewFactory() processor.Factory {
	return processor.NewFactory(
		component.MustNewType(typeStr),
		createDefaultConfig,
		processor.WithTraces(createTracesProcessor, metadata.TracesStability),
		processor.WithMetrics(createMetricsProcessor, metadata.MetricsStability),
		processor.WithLogs(createLogsProcessor, metadata.LogsStability),
	)
}

func createDefaultConfig() component.Config {
	return &shelper.Config{
		Source:         shelper.SlurmCtld,
		CacheDuration:  60,
		CacheFilepath:  "/tmp/slurmprocessor_cache.json",
		QuerySlurmCtld: false,
	}
}

func createTracesProcessor(
	ctx context.Context,
	set processor.Settings,
	cfg component.Config,
	nextTracesConsumer consumer.Traces,
) (processor.Traces, error) {
	log.Println("Creating Trace Processor")
	st := newSlurmInfoTraces(nextTracesConsumer, cfg)

	return processorhelper.NewTraces(
		ctx,
		set,
		cfg,
		nextTracesConsumer,
		st.processTraces,
		processorhelper.WithCapabilities(st.Capabilities()),
		processorhelper.WithStart(st.Start),
		processorhelper.WithShutdown(st.Shutdown))
}

func createMetricsProcessor(
	ctx context.Context,
	set processor.Settings,
	cfg component.Config,
	nextMetricsConsumer consumer.Metrics,
) (processor.Metrics, error) {
	log.Println("Creating Metrics Processor")
	sm := newSlurmInfoMetrics(nextMetricsConsumer, cfg)

	return processorhelper.NewMetrics(
		ctx,
		set,
		cfg,
		nextMetricsConsumer,
		sm.processMetrics,
		processorhelper.WithCapabilities(sm.Capabilities()),
		processorhelper.WithStart(sm.Start),
		processorhelper.WithShutdown(sm.Shutdown))
}

func createLogsProcessor(
	ctx context.Context,
	set processor.Settings,
	cfg component.Config,
	nextLogsConsumer consumer.Logs,
) (processor.Logs, error) {
	log.Println("Creating Logs Processor")
	sm := newSlurmInfoLogs(nextLogsConsumer, cfg)

	return processorhelper.NewLogs(
		ctx,
		set,
		cfg,
		nextLogsConsumer,
		sm.processLogs,
		processorhelper.WithCapabilities(sm.Capabilities()),
		processorhelper.WithStart(sm.Start),
		processorhelper.WithShutdown(sm.Shutdown))
}
