// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
)

func doesPIDExist(pid string, procFsRoot string) bool {
	_, err := os.Stat(filepath.Join(procFsRoot, pid))
	return err == nil
}

func getProcEnvStr(pid string, procFsRoot string) (string, error) {
	if !doesPIDExist(pid, procFsRoot) {
		formattedString := fmt.Sprintf("getProcEnvStr error: PID %s does not exist.\n", pid)
		log.Print(formattedString)
		return "", errors.New(formattedString)
	}

	envPath := filepath.Join(procFsRoot, pid, "environ")
	envBytes, err := os.ReadFile(envPath)
	if err != nil {
		log.Printf("getProcEnvStr warning: Could not read environment file for PID %s. Skipping.\n", pid)
		return "", err
	}

	return string(envBytes), nil
}

func parseVarFromProcEnvStr(env string, varName string) (string, error) {
	env = strings.TrimSuffix(env, "\x00")
	lines := strings.Split(env, "\x00")
	for _, line := range lines {
		if line == "" {
			continue
		}
		parts := strings.Split(line, "=")
		if len(parts) != 2 {
			log.Printf("Warning: proc environ line: '%s' does not conform to expected format", line)
		} else if parts[0] == varName {
			return parts[1], nil
		}
	}
	return "", fmt.Errorf("could not find %s in proc environ", varName)
}

func parseProcEnvStrToMap(env string) map[string]string {
	envMap := make(map[string]string)

	env = strings.TrimSuffix(env, "\x00")
	lines := strings.Split(env, "\x00")
	for _, line := range lines {
		if line == "" {
			continue
		}
		parts := strings.Split(line, "=")
		if len(parts) == 2 {
			envMap[parts[0]] = parts[1]
		} else {
			log.Printf("Warning: '%s' does not conform to expected format", line)
		}
	}
	return envMap
}

func parseSlurmMetadataFromProcEnv(pid string) (SlurmMetadata, error) {
	log.Printf("scraping envvars for pid: %s\n", pid)
	env, err := getProcEnvStr(pid, "/proc")
	if err != nil {
		return SlurmMetadata{}, err
	}
	envMap := parseProcEnvStrToMap(env)
	return SlurmMetadata{
		JobID:       envMap["SLURM_JOB_ID"],
		JobName:     envMap["SLURM_JOB_NAME"],
		QOS:         envMap["SLURM_JOB_QOS"],
		User:        envMap["SLURM_JOB_USER"],
		Partition:   envMap["SLURM_JOB_PARTITION"],
		Account:     envMap["SLURM_JOB_ACCOUNT"],
		NumNodes:    envMap["SLURM_JOB_NUM_NODES"],
		ArrayJobID:  envMap["SLURM_ARRAY_JOB_ID"],
		ArrayTaskID: envMap["SLURM_ARRAY_TASK_ID"],
	}, nil
}
