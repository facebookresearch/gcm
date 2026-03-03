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
	jobIDs := []string{}

	if err != nil {
		return jobIDs, err
	}
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
		err = fmt.Errorf("%w: %v", cmdErr, stderr.String())
		return jobIDs, err
	}

	jobIDs = parseNewLineToList(out.String())
	return jobIDs, nil
}
