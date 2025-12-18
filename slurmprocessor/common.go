// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package main

import (
	"context"
	"log"
	"strings"

	shelper "github.com/fairinternal/fair-cluster-monitoring/shelper"
	"go.opentelemetry.io/collector/component"
	"go.opentelemetry.io/collector/consumer"
	"go.opentelemetry.io/collector/pdata/pcommon"
)

// SlurmJobID is used as the attribute key for slurm job id
const SlurmJobID = "job_id"

// SlurmJobName is used as the attribute key for slurm job name
const SlurmJobName = "job_name"

// SlurmQOS is used as the attribute key for slurm QOS associated with the job
const SlurmQOS = "qos"

// ArrayJobID is used as the attribute key for slurm array job id
const SlurmArrayJobID = "array_job_id"

// ArrayTaskID is used as the attribute key for slurm array task id
const SlurmArrayTaskID = "array_task_id"

// SlurmUser is used as the attribute key for slurm username
const SlurmUser = "username"

// SlurmPartition is used as the attribute key for slurm partition associated with the job
const SlurmPartition = "partition"

// SlurmAccount is used as the attribute key for slurm account associated with the job
const SlurmAccount = "account"

// SlurmNNodes is used as the attribute key for slurm number of nodes assigned to the job
const SlurmNNodes = "num_nodes"

// gpuUUID is used as the attribute key for GPU UUID
const gpuUUID = "uuid"

// SlurmProcessorBase contains common fields and methods for all slurm processors
type SlurmProcessorBase struct {
	// The configuration for the processor
	Config *shelper.Config
}

// NewSlurmProcessorBase creates a new SlurmProcessorBase with the given config
func NewSlurmProcessorBase(cfg component.Config) SlurmProcessorBase {
	return SlurmProcessorBase{
		Config: cfg.(*shelper.Config),
	}
}

// Capabilities returns the capabilities of the processor
func (spb *SlurmProcessorBase) Capabilities() consumer.Capabilities {
	return consumer.Capabilities{MutatesData: true}
}

// Start is called when the processor starts
func (spb *SlurmProcessorBase) Start(_ context.Context, _ component.Host) error {
	log.Println("Starting slurm processor")
	return nil
}

// Shutdown is called when the processor shuts down
func (spb *SlurmProcessorBase) Shutdown(context.Context) error {
	log.Println("Shutting down slurm processor")
	return nil
}

// AggregateSlurmJobIDs adds the slurm job IDs to the resource attributes
func (spb *SlurmProcessorBase) AggregateSlurmJobIDs(resource pcommon.Resource, slurmJobIDs []string) {
	joinedSlurmJobIDs := strings.Join(slurmJobIDs, ",")
	if joinedSlurmJobIDs != "" {
		resource.Attributes().PutStr(SlurmJobID, joinedSlurmJobIDs)
	}
}

// AddSlurmMetadataStr adds slurm metadata to attributes as string values
func (spb *SlurmProcessorBase) AddSlurmMetadataStr(attributes pcommon.Map, slurmMetadata shelper.SlurmMetadata) {
	columnMap := map[string]string{
		SlurmJobID:       slurmMetadata.JobID,
		SlurmJobName:     slurmMetadata.JobName,
		SlurmQOS:         slurmMetadata.QOS,
		SlurmArrayJobID:  slurmMetadata.ArrayJobID,
		SlurmArrayTaskID: slurmMetadata.ArrayTaskID,
		SlurmUser:        slurmMetadata.User,
		SlurmPartition:   slurmMetadata.Partition,
		SlurmAccount:     slurmMetadata.Account,
		SlurmNNodes:      slurmMetadata.NumNodes,
	}

	for name, value := range columnMap {
		attributes.PutStr(name, value)
	}
}

// AddSlurmMetadataSlice adds slurm metadata to attributes as slice values
func (spb *SlurmProcessorBase) AddSlurmMetadataSlice(attributes pcommon.Map, allGPUData shelper.SlurmMetadataList) {
	columnMap := map[string][]string{
		SlurmJobID:       allGPUData.JobID,
		SlurmJobName:     allGPUData.JobName,
		SlurmQOS:         allGPUData.QOS,
		SlurmArrayJobID:  allGPUData.ArrayJobID,
		SlurmArrayTaskID: allGPUData.ArrayTaskID,
		SlurmUser:        allGPUData.User,
		SlurmPartition:   allGPUData.Partition,
		SlurmAccount:     allGPUData.Account,
		SlurmNNodes:      allGPUData.NumNodes,
	}

	for name, value := range columnMap {
		es := attributes.PutEmptySlice(name)
		for _, v := range value {
			es.AppendEmpty().SetStr(v)
		}
	}
}
