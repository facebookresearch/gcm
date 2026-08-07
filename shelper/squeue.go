// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"bytes"
	"fmt"
	"os/exec"
)

// GetSlurmJobIDsSqueue queries slurmctld for the job ids of all jobs running on this host, it returns a comma separated string of job ids.
func GetSlurmJobIDsSqueue() ([]string, error) {
	hostname, err := GetHostname()
	if err != nil {
		return []string{}, err
	}
	return GetSlurmJobIDsSqueueForHost(hostname)
}

// GetSlurmJobIDsSqueueForHost queries slurmctld for the job ids of all jobs
// running on the given host. Unlike `scontrol listpids`, this does not need a
// node-local slurmd, so callers that already know the Slurm node name (for
// example from SLURMD_NODENAME on Kubernetes, where the OS hostname differs
// from Slurm's NodeList) can run in a separate container or Pod.
func GetSlurmJobIDsSqueueForHost(hostname string) ([]string, error) {
	jobIDs := []string{}

	// -h: remove slurm headers from output
	// -w <hostname>: only get jobs running on the given host
	// -o <field>: output only the given field
	//    %i: job id
	cmd := exec.Command("squeue", "-h", "-w", hostname, "-o", "%i")

	var out bytes.Buffer
	cmd.Stdout = &out

	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	cmdErr := cmd.Run()
	if cmdErr != nil {
		return jobIDs, fmt.Errorf("%w: %v", cmdErr, stderr.String())
	}

	jobIDs = parseNewLineToList(out.String())
	return jobIDs, nil
}
