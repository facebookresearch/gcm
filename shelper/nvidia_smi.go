// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"bufio"
	"context"
	"log"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

// Keep both GPU index and PID: pmon may emit multiple rows for one GPU,
// and row position is not a GPU index. DCGM uses the physical GPU index.
const NvidiaSmiGetPidsCommand = "nvidia-smi pmon -c 1"

func GetGPU2SlurmFromNvml(GPU2Slurm map[string]SlurmMetadata) {
	output, err := executeGpuPidsCommand()
	if err != nil {
		log.Printf("GetGPU2SlurmFromNvml error executing command to get PIDs running on the GPUs: %s\n", err)
		return
	}
	gpuToPid := parseNvidiaSmiGetPidsCommand(output)
	for gpuID, pids := range gpuToPid {
		if metadata, ok := metadataForGPU(pids, parseSlurmMetadataFromProcEnv); ok {
			GPU2Slurm[gpuID] = metadata
		}
	}
}

// A GPU can run several processes belonging to the same allocation. Only
// attribute a GPU when every observed process agrees on its Slurm metadata.
// Missing/disappearing processes and different jobs must not pick an arbitrary
// owner for a whole-GPU measurement.
func metadataForGPU(pids []string, readMetadata func(string) (SlurmMetadata, error)) (SlurmMetadata, bool) {
	var metadata SlurmMetadata
	for i, pid := range pids {
		current, err := readMetadata(pid)
		if err != nil || current.JobID == "" {
			return SlurmMetadata{}, false
		}
		if i > 0 && current != metadata {
			return SlurmMetadata{}, false
		}
		metadata = current
	}
	return metadata, len(pids) > 0
}

func executeGpuPidsCommand() (string, error) {
	// Do not let an unresponsive driver stall the metrics pipeline indefinitely.
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "nvidia-smi", "pmon", "-c", "1")
	outputBytes, err := cmd.CombinedOutput()
	if err != nil {
		return "", err
	}
	return string(outputBytes), nil
}

func parseNvidiaSmiGetPidsCommand(output string) map[string][]string {
	gpuToPid := make(map[string][]string)
	scanner := bufio.NewScanner(strings.NewReader(output))
	for scanner.Scan() {
		fields := strings.Fields(scanner.Text())
		if len(fields) < 2 {
			continue
		}
		gpu, gpuErr := strconv.Atoi(fields[0])
		pid, pidErr := strconv.Atoi(fields[1])
		if gpuErr != nil || pidErr != nil || gpu < 0 || pid <= 0 {
			continue
		}
		gpuID := strconv.Itoa(gpu)
		gpuToPid[gpuID] = append(gpuToPid[gpuID], strconv.Itoa(pid))
	}

	return gpuToPid
}
