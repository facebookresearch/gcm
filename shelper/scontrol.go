// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"bufio"
	"log"
	"strings"

	"os/exec"
)

// GetJobMetadata queries scontrol, it returns a list of job metadata
func GetJobMetadata(JobID string) ([]string, error) {
	blocks := []string{}
	outputBytes, err := exec.Command("scontrol", "show", "jobs", JobID, "-d").CombinedOutput()
	if err != nil {
		log.Printf("GetJob error: %s, output: %s\n", err, outputBytes)
		return blocks, err
	}
	output := string(outputBytes)
	blocks = strings.Split(output, "\n\n")
	return blocks, nil
}

// GetJob2Pid queries slurmd, it returns a map of slurm job id to pid.
func GetJob2Pid() (map[string]string, []string, error) {
	pidMappings := make(map[string]string)
	jobIDs := []string{}

	pidMappingsOutput, err := exec.Command("scontrol", "listpids").CombinedOutput()
	if err != nil {
		log.Printf("GetSlurmJobIDsScontrol error: %s, output: %s\n", err, pidMappingsOutput)
		return pidMappings, jobIDs, err
	}

	scanner := bufio.NewScanner(strings.NewReader(string(pidMappingsOutput)))
	scanner.Scan() // this skips the first row of scontrol output which is just column headers
	for scanner.Scan() {
		fields := strings.Fields(scanner.Text())
		if len(fields) < 2 {
			continue
		}
		slurmJobID, pid := fields[1], fields[0]
		// Only store the first PID for each Slurm job ID
		if _, ok := pidMappings[slurmJobID]; !ok {
			pidMappings[slurmJobID] = pid
			jobIDs = append(jobIDs, slurmJobID)
		}
	}

	if len(pidMappings) == 0 {
		log.Println("genSidToGPUMapping warning: No Slurm jobs found on the host.")
	}

	return pidMappings, jobIDs, nil
}
