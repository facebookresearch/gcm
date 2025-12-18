// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package main

import (
	"context"
	"log"

	shelper "github.com/fairinternal/fair-cluster-monitoring/shelper"
	"go.opentelemetry.io/collector/component"
	"go.opentelemetry.io/collector/consumer"
	"go.opentelemetry.io/collector/pdata/plog"
)

type slurmInfoLogs struct {
	next consumer.Logs
	SlurmProcessorBase
}

func newSlurmInfoLogs(next consumer.Logs, cfg component.Config) *slurmInfoLogs {
	return &slurmInfoLogs{
		next:               next,
		SlurmProcessorBase: NewSlurmProcessorBase(cfg),
	}
}

func (sl *slurmInfoLogs) processLogs(ctx context.Context, logs plog.Logs) (plog.Logs, error) {
	resourceLogsSlice := logs.ResourceLogs()
	var GPUToSlurmMetadata map[string]shelper.SlurmMetadata
	var slurmJobIDs []string
	var err error

	GPUToSlurmMetadata, slurmJobIDs, err = shelper.GetGPU2Slurm(sl.Config)
	if err != nil {
		log.Println("Error getting per GPU slurm job ids: ", err)
	}

	for i := 0; i < resourceLogsSlice.Len(); i++ {
		sl.AggregateSlurmJobIDs(resourceLogsSlice.At(i).Resource(), slurmJobIDs)
		scopeLogsSlice := resourceLogsSlice.At(i).ScopeLogs()

		for j := 0; j < scopeLogsSlice.Len(); j++ {
			logRecordsSlice := scopeLogsSlice.At(j).LogRecords()

			for k := 0; k < logRecordsSlice.Len(); k++ {
				logRecord := logRecordsSlice.At(k)
				sl.aggregateGPUSpecificSlurmMetadata(logRecord, GPUToSlurmMetadata)
			}
		}
	}

	return logs, nil
}

func (sl *slurmInfoLogs) aggregateGPUSpecificSlurmMetadata(log plog.LogRecord, GPUToSlurmMetadata map[string]shelper.SlurmMetadata) {
	GPUIndexValue, containsGPUIndex := log.Attributes().Get("gpu")
	GPUIndexStr := GPUIndexValue.Str()
	if containsGPUIndex {
		if slurmMetadata, ok := GPUToSlurmMetadata[GPUIndexStr]; ok {
			sl.AddSlurmMetadataStr(log.Attributes(), slurmMetadata)
		}
	}
}
