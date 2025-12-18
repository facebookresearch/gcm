// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"bufio"
	"fmt"
	"log"
	"os/exec"
	"strings"
)

// In the future we should use `nvidia-smi --query-compute-apps=pid,gpu_uuid --format=csv,noheader` since this is a "structured" output
// For now we rely on parsing pmon's text output because the "preferable" approach above only provides the GPU UUID, not the index.
// Currently the logic to correlate SLURM metadata with DCGM metrics is based on the GPU index, not the UUID.
const NvidiaSmiGetPidsCommand = "nvidia-smi pmon -c 1 | awk '{print $2}' | tail -n +3"

func GetGPU2SlurmFromNvml(GPU2Slurm map[string]SlurmMetadata) {
	output, err := executeGpuPidsCommand()
	if err != nil {
		log.Printf("GetGPU2SlurmFromNvml error executing command to get PIDs running on the GPUs: %s\n", err)
		return
	}
	log.Printf("GetGPU2SlurmFromNvml output: %s\n", output)
	gpuToPid := parseNvidiaSmiGetPidsCommand(output)
	// for each PID, call `parseSlurmMetadataFromProcEnv` and map the corresponding GPU to the Slurm metadata
	for gpuID, pid := range gpuToPid {
		if pid == "" {
			continue
		}
		slurmMetadata, err := parseSlurmMetadataFromProcEnv(pid)
		if err != nil {
			log.Printf("GetGPU2SlurmFromNvml error parsing Slurm metadata for PID %s: %s\n", pid, err)
			GPU2Slurm[gpuID] = SlurmMetadata{}
			continue
		}
		GPU2Slurm[gpuID] = slurmMetadata
	}
}

func executeGpuPidsCommand() (string, error) {
	// Execute the nvidia-smi command to get PIDs running on GPUs
	cmd := exec.Command("sh", "-c", NvidiaSmiGetPidsCommand)
	outputBytes, err := cmd.CombinedOutput()
	if err != nil {
		return "", err
	}
	return string(outputBytes), nil
}

func parseNvidiaSmiGetPidsCommand(output string) map[string]string {
	gpuToPid := make(map[string]string)
	// Parse the output line by line
	scanner := bufio.NewScanner(strings.NewReader(output))
	gpuID := 0
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		// Extract numerical values until a non-numerical character
		var numStr string
		for _, char := range line {
			if char >= '0' && char <= '9' {
				numStr += string(char)
			} else {
				break
			}
		}
		gpuToPid[fmt.Sprintf("%d", gpuID)] = numStr
		gpuID++
	}

	return gpuToPid
}
