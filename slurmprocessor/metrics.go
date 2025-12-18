// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package main

import (
	"context"
	"log"

	shelper "github.com/fairinternal/fair-cluster-monitoring/shelper"
	"go.opentelemetry.io/collector/component"
	"go.opentelemetry.io/collector/consumer"
	"go.opentelemetry.io/collector/pdata/pmetric"
)

type slurmInfoMetrics struct {
	next consumer.Metrics
	SlurmProcessorBase
}

func newSlurmInfoMetrics(next consumer.Metrics, cfg component.Config) *slurmInfoMetrics {
	return &slurmInfoMetrics{
		next:               next,
		SlurmProcessorBase: NewSlurmProcessorBase(cfg),
	}
}

func (sm *slurmInfoMetrics) processMetrics(ctx context.Context, metrics pmetric.Metrics) (pmetric.Metrics, error) {
	resourceMetricsSlice := metrics.ResourceMetrics()
	var GPU2Slurm map[string]shelper.SlurmMetadata
	//var slurmJobIDs []string
	var err error

	GPU2Slurm, _, err = shelper.GetGPU2Slurm(sm.Config)
	if err != nil {
		log.Println("Error getting per GPU slurm job ids: ", err)
	}

	for i := range resourceMetricsSlice.Len() {
		scopeMetricsSlice := resourceMetricsSlice.At(i).ScopeMetrics()

		for j := range scopeMetricsSlice.Len() {
			metricsSlice := scopeMetricsSlice.At(j).Metrics()

			for k := range metricsSlice.Len() {
				metric := metricsSlice.At(k)

				switch metric.Type() {
				case pmetric.MetricTypeGauge:
					datapoints := metric.Gauge().DataPoints()
					sm.aggregateSlurmToGaugeOrSum(datapoints, GPU2Slurm)

				case pmetric.MetricTypeSum:
					datapoints := metric.Sum().DataPoints()
					sm.aggregateSlurmToGaugeOrSum(datapoints, GPU2Slurm)

				case pmetric.MetricTypeHistogram:
					datapoints := metric.Histogram().DataPoints()
					sm.aggregateSlurmToHistogram(datapoints, GPU2Slurm)

				case pmetric.MetricTypeExponentialHistogram:
					datapoints := metric.ExponentialHistogram().DataPoints()
					sm.aggregateSlurmToExponentialHistogram(datapoints, GPU2Slurm)

				case pmetric.MetricTypeSummary:
					datapoints := metric.Summary().DataPoints()
					sm.aggregateSlurmToSummary(datapoints, GPU2Slurm)
				}
			}
		}
	}

	return metrics, nil
}

func (sm *slurmInfoMetrics) aggregateSlurmToGaugeOrSum(datapoints pmetric.NumberDataPointSlice, GPUToSlurm map[string]shelper.SlurmMetadata) {
	for l := range datapoints.Len() {
		GPUIndexValue, containsGPUIndex := datapoints.At(l).Attributes().Get("gpu")
		GPUIndexStr := GPUIndexValue.Str()

		if containsGPUIndex {
			if slurmMetadata, ok := GPUToSlurm[GPUIndexStr]; ok {
				sm.AddSlurmMetadataStr(datapoints.At(l).Attributes(), slurmMetadata)
			}
		} else {
			// Aggregate Metadata about all slurm jobs on the node
			allGPUData := shelper.GetGPUData(GPUToSlurm)
			sm.AddSlurmMetadataSlice(datapoints.At(l).Attributes(), allGPUData)
		}
		uuidIndexValue, containsuuidIndex := datapoints.At(l).Attributes().Get("UUID")
		uuidStr := uuidIndexValue.Str()

		if containsuuidIndex {
			datapoints.At(l).Attributes().PutStr(gpuUUID, uuidStr)
		}
	}
}

func (sm *slurmInfoMetrics) aggregateSlurmToHistogram(datapoints pmetric.HistogramDataPointSlice, GPUToSlurm map[string]shelper.SlurmMetadata) {
	for l := range datapoints.Len() {
		GPUIndexValue, containsGPUIndex := datapoints.At(l).Attributes().Get("gpu")
		GPUIndexStr := GPUIndexValue.Str()

		if containsGPUIndex {
			if slurmMetadata, ok := GPUToSlurm[GPUIndexStr]; ok {
				sm.AddSlurmMetadataStr(datapoints.At(l).Attributes(), slurmMetadata)
			}
		} else {
			// Aggregate Metadata about all slurm jobs on the node
			allGPUData := shelper.GetGPUData(GPUToSlurm)
			sm.AddSlurmMetadataSlice(datapoints.At(l).Attributes(), allGPUData)
		}
		uuidIndexValue, containsuuidIndex := datapoints.At(l).Attributes().Get("UUID")
		uuidStr := uuidIndexValue.Str()

		if containsuuidIndex {
			datapoints.At(l).Attributes().PutStr(gpuUUID, uuidStr)
		}
	}
}

func (sm *slurmInfoMetrics) aggregateSlurmToExponentialHistogram(datapoints pmetric.ExponentialHistogramDataPointSlice, GPUToSlurm map[string]shelper.SlurmMetadata) {
	for l := range datapoints.Len() {
		GPUIndexValue, containsGPUIndex := datapoints.At(l).Attributes().Get("gpu")
		GPUIndexStr := GPUIndexValue.Str()

		if containsGPUIndex {
			if slurmMetadata, ok := GPUToSlurm[GPUIndexStr]; ok {
				sm.AddSlurmMetadataStr(datapoints.At(l).Attributes(), slurmMetadata)
			}
		} else {
			// Aggregate Metadata about all slurm jobs on the node
			allGPUData := shelper.GetGPUData(GPUToSlurm)
			sm.AddSlurmMetadataSlice(datapoints.At(l).Attributes(), allGPUData)
		}
		uuidIndexValue, containsuuidIndex := datapoints.At(l).Attributes().Get("UUID")
		uuidStr := uuidIndexValue.Str()

		if containsuuidIndex {
			datapoints.At(l).Attributes().PutStr(gpuUUID, uuidStr)
		}
	}
}

func (sm *slurmInfoMetrics) aggregateSlurmToSummary(datapoints pmetric.SummaryDataPointSlice, GPUToSlurm map[string]shelper.SlurmMetadata) {
	for l := range datapoints.Len() {
		GPUIndexValue, containsGPUIndex := datapoints.At(l).Attributes().Get("gpu")
		GPUIndexStr := GPUIndexValue.Str()

		if containsGPUIndex {
			if slurmMetadata, ok := GPUToSlurm[GPUIndexStr]; ok {
				sm.AddSlurmMetadataStr(datapoints.At(l).Attributes(), slurmMetadata)
			}
		} else {
			// Aggregate Metadata about all slurm jobs on the node
			allGPUData := shelper.GetGPUData(GPUToSlurm)
			sm.AddSlurmMetadataSlice(datapoints.At(l).Attributes(), allGPUData)
		}
		uuidIndexValue, containsuuidIndex := datapoints.At(l).Attributes().Get("UUID")
		uuidStr := uuidIndexValue.Str()

		if containsuuidIndex {
			datapoints.At(l).Attributes().PutStr(gpuUUID, uuidStr)
		}
	}
}
