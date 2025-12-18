// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"encoding/json"
	"log"
)

// GetGPU2Slurm receives a Config struct and returns a map of gpu to SlurmMetadata.
// This is the preferred method for getting GPU to Slurm metadata mapping.
func GetGPU2Slurm(cfg *Config) (map[string]SlurmMetadata, []string, error) {
	// Get the metadata source
	source := cfg.GetMetadataSource()
	var jobIDs []string
	var err error
	GPU2Slurm := make(map[string]SlurmMetadata)

	hostname, err := GetHostname()
	if err != nil {
		return GPU2Slurm, jobIDs, err
	}
	log.Printf("Metadata source: %v\n", source)
	switch source {
	case Nvml:
		// T239461118: Extract jobIDs from GPU2Slurm
		GetGPU2SlurmFromNvml(GPU2Slurm)
	case SlurmCtld:
		_, jobIDs, err = GetJob2Pid()
		if err != nil {
			return GPU2Slurm, jobIDs, err
		}
		// Only access cache-related values when in SlurmCtld mode
		cacheDuration := cfg.GetCacheDuration()
		cacheFilepath := cfg.GetCacheFilepath()

		// caches will out live jobs which means the first n minutes and last n minutes
		// of metrics will be invalid for a given job. Should be okay since jobs tend to
		// not use gpus during start up and tear down
		data, err := GetSlurmMetadataCache(cacheFilepath, cacheDuration)
		if err != nil {
			log.Println("Error reading cache:", err)
			return GPU2Slurm, jobIDs, err
		}

		// if cache is not valid, query slurmctld and write to cache
		if data == "" {
			for _, jobID := range jobIDs {
				jobMetadata, err := GetJobMetadata(jobID)
				if err != nil {
					log.Println("Error querying scontrol show jobs:", err)
					return GPU2Slurm, jobIDs, err
				}
				AttributeGPU2SlurmMetadata(jobMetadata, hostname, GPU2Slurm)
			}

			err = SaveSlurmToJSON(cacheFilepath, GPU2Slurm)
			if err != nil {
				log.Println("Error saving to local filesystem cache:", err)
				return GPU2Slurm, jobIDs, err
			}
		} else {
			err = json.Unmarshal([]byte(data), &GPU2Slurm)
			if err != nil {
				return GPU2Slurm, jobIDs, err
			}
		}
	case Slurmd:
		var job2pid map[string]string
		job2pid, jobIDs, err = GetJob2Pid()
		if err != nil {
			return GPU2Slurm, jobIDs, err
		}
		GPU2Slurm, err = GetGPU2SlurmFromPIDs(job2pid)
		if err != nil {
			return GPU2Slurm, jobIDs, err
		}
	default:
		log.Printf("Error: Unexpected metadata source: %v", source)
	}
	return GPU2Slurm, jobIDs, err
}
