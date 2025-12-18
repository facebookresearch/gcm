// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"fmt"
	"log"
	"os/exec"
	"strings"
)

// SlurmMetadata is a struct that contains metadata about a slurm job
type SlurmMetadata struct {
	JobID       string `json:"JobID"`
	JobName     string `json:"JobName"`
	QOS         string `json:"QOS"`
	User        string `json:"User"`
	Partition   string `json:"Partition"`
	Account     string `json:"Account"`
	NumNodes    string `json:"NumNodes"`
	ArrayJobID  string `json:"ArrayJobID"`
	ArrayTaskID string `json:"ArrayTaskID"`
}

// SlurmMetadataList is a struct that contains metadata about a slurm job
type SlurmMetadataList struct {
	JobID       []string
	JobName     []string
	QOS         []string
	User        []string
	Partition   []string
	Account     []string
	NumNodes    []string
	ArrayJobID  []string
	ArrayTaskID []string
}

func parseNewLineToList(input string) []string {
	jobIDs := strings.Split(strings.TrimSpace(input), "\n")
	return jobIDs
}

func getUser(pid string) (string, error) {
	cmd := exec.Command("ps", "-o", "user", "-p", pid, "--no-headers")

	var user string

	output, err := cmd.Output()
	if err != nil {
		fmt.Printf("Error: %s\n", err)
		return user, err
	}

	user = strings.TrimSpace(string(output))
	return user, nil
}

func getGPUsFromEnv(env string) []string {
	gpus := []string{}
	gpusStr, err := parseVarFromProcEnvStr(env, "SLURM_JOB_GPUS")
	if err == nil {
		gpus = strings.Split(strings.Trim(gpusStr, ", "), ",")
	}
	return gpus
}

// GetGPU2SlurmFromPIDs receives a map of slurm job ID to PID and returns a map of GPU index to SlurmMetadata.
func GetGPU2SlurmFromPIDs(slurmJobIDsToPIDs map[string]string) (map[string]SlurmMetadata, error) {
	GPU2Slurm := make(map[string]SlurmMetadata)

	for slurmJobID, pid := range slurmJobIDsToPIDs {
		log.Printf("scraping envvars for slurm job: %s, pid: %s\n", slurmJobID, pid)
		env, err := getProcEnvStr(pid, "/proc")
		if err != nil {
			log.Printf("GetGPU2SlurmFromPIDs warning: Could not read envvars for PID %s", pid)
			return GPU2Slurm, err
		}
		gpus := getGPUsFromEnv(env)
		if len(gpus) == 0 {
			log.Printf("GetGPU2SlurmFromPIDs warning: SLURM_JOB_GPUS not defined for PID %s. Skipping.\n", pid)
			return GPU2Slurm, err
		}
		log.Printf("SLURM_JOB_GPUS defined for PID %s. Skipping.\n", pid)
		user, err := getUser(pid)
		if err != nil {
			log.Printf("GetGPU2SlurmFromPIDs warning: Could not read Slurm User for PID %s. Skipping.\n", pid)
		}

		for i := range gpus {
			GPU2Slurm[gpus[i]] = SlurmMetadata{
				JobID: slurmJobID,
				User:  user,
			}
		}
	}

	return GPU2Slurm, nil
}
