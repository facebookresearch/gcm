// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package main

import (
	"context"
	"log"

	shelper "github.com/fairinternal/fair-cluster-monitoring/shelper"
	"go.opentelemetry.io/collector/component"
	"go.opentelemetry.io/collector/consumer"
	"go.opentelemetry.io/collector/pdata/ptrace"
)

type slurmInfoTraces struct {
	next consumer.Traces
	SlurmProcessorBase
}

func newSlurmInfoTraces(next consumer.Traces, cfg component.Config) *slurmInfoTraces {
	return &slurmInfoTraces{
		next:               next,
		SlurmProcessorBase: NewSlurmProcessorBase(cfg),
	}
}

func (st *slurmInfoTraces) processTraces(ctx context.Context, traces ptrace.Traces) (ptrace.Traces, error) {
	resourceSpansSlice := traces.ResourceSpans()
	var GPU2Slurm map[string]shelper.SlurmMetadata
	var slurmJobIDs []string
	var err error

	GPU2Slurm, slurmJobIDs, err = shelper.GetGPU2Slurm(st.Config)
	if err != nil {
		log.Println("Error getting per GPU slurm job ids: ", err)
	}

	for i := 0; i < resourceSpansSlice.Len(); i++ {
		st.AggregateSlurmJobIDs(resourceSpansSlice.At(i).Resource(), slurmJobIDs)
		scopeSpansSlice := resourceSpansSlice.At(i).ScopeSpans()

		for j := 0; j < scopeSpansSlice.Len(); j++ {
			spanSlice := scopeSpansSlice.At(j).Spans()

			for k := 0; k < spanSlice.Len(); k++ {
				span := spanSlice.At(k)
				st.aggregateGPUSpecificSlurmMetadata(span, GPU2Slurm)
			}
		}
	}

	return traces, nil
}

func (st *slurmInfoTraces) aggregateGPUSpecificSlurmMetadata(span ptrace.Span, GPUToSlurmMetadata map[string]shelper.SlurmMetadata) {
	GPUIndexValue, containsGPUIndex := span.Attributes().Get("gpu")
	GPUIndexStr := GPUIndexValue.Str()
	if containsGPUIndex {
		if slurmMetadata, ok := GPUToSlurmMetadata[GPUIndexStr]; ok {
			st.AddSlurmMetadataStr(span.Attributes(), slurmMetadata)
		}
	}
}
