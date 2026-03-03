// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"log"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

func parseGRES(gresOut string) []string {
	re := regexp.MustCompile(`\(([^)]+)\)`)
	gpuIndices := []string{}

	indicesKey := re.FindStringSubmatch(gresOut)

	if len(indicesKey) < 2 {
		log.Printf("parseGRES warning: parsing gpu index range (likely empty): %s\n", indicesKey)
		return gpuIndices
	}

	indexString := strings.SplitN(indicesKey[1], ":", 2)[1]
	indices := strings.Split(indexString, ",")

	for _, index := range indices {
		if strings.Contains(index, "-") {
			indexRange := strings.Split(index, "-")
			st, err1 := strconv.Atoi(indexRange[0])
			end, err2 := strconv.Atoi(indexRange[1])
			if err1 != nil || err2 != nil {
				log.Printf("parseGRES error: parsing gpu index range: %s, %s\n", err1, err2)
				continue
			}

			for i := st; i <= end; i++ {
				gpuIndices = append(gpuIndices, strconv.Itoa(i))
			}
		} else if _, err := strconv.Atoi(index); err == nil {
			gpuIndices = append(gpuIndices, index)
		}
	}

	return gpuIndices
}

func stringifySet(set map[string]bool) string {
	var result []string
	for k := range set {
		result = append(result, k)
	}
	sort.Strings(result)
	return strings.Join(result, ",")
}

func setToSlice(set map[string]bool) []string {
	result := make([]string, 0, len(set))
	for key := range set {
		result = append(result, key)
	}
	sort.Strings(result)
	return result
}

// GetGPUData returns a map of all slurm job ids, job names, qos, array job ids, array task ids
func GetGPUData(GPUToSlurm map[string]SlurmMetadata) SlurmMetadataList {
	allJobID := make(map[string]bool)
	allJobName := make(map[string]bool)
	allQOS := make(map[string]bool)
	allArrayJobID := make(map[string]bool)
	allArrayTaskID := make(map[string]bool)
	allUsers := make(map[string]bool)
	allPartition := make(map[string]bool)
	allAccount := make(map[string]bool)
	allNumNodes := make(map[string]bool)
	for _, value := range GPUToSlurm {
		allJobID[value.JobID] = true
		allJobName[value.JobName] = true
		allQOS[value.QOS] = true
		allArrayJobID[value.ArrayJobID] = true
		allArrayTaskID[value.ArrayTaskID] = true
		allUsers[value.User] = true
		allPartition[value.Partition] = true
		allAccount[value.Account] = true
		allNumNodes[value.NumNodes] = true
	}
	return SlurmMetadataList{
		JobID:       setToSlice(allJobID),
		JobName:     setToSlice(allJobName),
		QOS:         setToSlice(allQOS),
		ArrayJobID:  setToSlice(allArrayJobID),
		ArrayTaskID: setToSlice(allArrayTaskID),
		User:        setToSlice(allUsers),
		Partition:   setToSlice(allPartition),
		Account:     setToSlice(allAccount),
		NumNodes:    setToSlice(allNumNodes),
	}
}

// AttributeGPU2SlurmMetadata takes a list of slurm job metadata and a hostname and GPU2Slurm pointer
// and populates the GPU2Slurm map with the slurm metadata for each GPU on the host
func AttributeGPU2SlurmMetadata(jobMetadata []string, hostname string, GPU2Slurm map[string]SlurmMetadata) {
	for _, jm := range jobMetadata {
		hostlist := GetHostList(jm)
		if !HostnameInList(hostname, hostlist) {
			// Skip this job metadata if it doesn't refer the current host
			continue
		}

		gresIndex := []string{}
		allUsers := make(map[string]bool)
		allJobID := make(map[string]bool)
		allJobName := make(map[string]bool)
		allQOS := make(map[string]bool)
		allArrayJobID := make(map[string]bool)
		allArrayTaskID := make(map[string]bool)
		allAccount := make(map[string]bool)
		allPartition := make(map[string]bool)
		allNumNodes := make(map[string]bool)

		lines := strings.Split(jm, "\n")
		for _, line := range lines {
			field := strings.Fields(line)

			for _, data := range field {
				parts := strings.SplitN(data, "=", 2)
				if parts[0] == "UserId" {
					end := strings.Index(parts[1], "(")
					user := parts[1][:end]
					allUsers[user] = true
				}
				if parts[0] == "JobId" {
					allJobID[parts[1]] = true
				}
				if parts[0] == "QOS" {
					allQOS[parts[1]] = true
				}
				if parts[0] == "JobName" {
					allJobName[parts[1]] = true
				}
				if parts[0] == "ArrayJobId" {
					allArrayJobID[parts[1]] = true
				}
				if parts[0] == "ArrayTaskId" {
					// if ArrayTaskID is not convertible to int it means that this slurm job metadata block
					// refers to the main slurm array job, there _should_ be another job running on this node so we can
					// safely ignore this line
					_, err := strconv.Atoi(parts[1])
					if err != nil {
						continue
					}
					allArrayTaskID[parts[1]] = true
				}
				if parts[0] == "Account" {
					allAccount[parts[1]] = true
				}
				if parts[0] == "Partition" {
					allPartition[parts[1]] = true
				}
				if parts[0] == "NumNodes" {
					allNumNodes[parts[1]] = true
				}
				if parts[0] == "GRES" {
					gresIndex = append(gresIndex, parseGRES(parts[1])...)
				}
			}
		}

		var slurm = SlurmMetadata{
			User:        stringifySet(allUsers),
			JobID:       stringifySet(allJobID),
			JobName:     stringifySet(allJobName),
			QOS:         stringifySet(allQOS),
			ArrayJobID:  stringifySet(allArrayJobID),
			ArrayTaskID: stringifySet(allArrayTaskID),
			Account:     stringifySet(allAccount),
			Partition:   stringifySet(allPartition),
			NumNodes:    stringifySet(allNumNodes),
		}

		for _, gpu := range gresIndex {
			GPU2Slurm[gpu] = slurm
		}
	}
}

// GetHostList takes a slurm job metadata string and returns the hostlist
func GetHostList(jobMetadata string) string {
	lines := strings.Split(jobMetadata, "\n")

	for _, line := range lines {
		field := strings.Fields(line)
		for _, data := range field {
			parts := strings.SplitN(data, "=", 2)
			if parts[0] == "NodeList" {
				return parts[1]
			}
		}
	}

	return ""
}

// HostnameInList takes a hostname and a slurm hostlist and returns true if the hostname is in the hostlist
func HostnameInList(hostname string, hostlist string) bool {
	// hostlist follows the slurm naming convention where
	// numeric ranges can be contained with ranges, e.g. node[1-5,7-9]
	// see https://github.com/SchedMD/slurm/blob/main/src/common/hostlist.h#L106-L145

	// if the hostlist is not a list, then we can just compare the hostnames
	if !strings.Contains(hostlist, "[") {
		if hostname == "" {
			return false
		}
		return hostlist == hostname
	}

	re := regexp.MustCompile(`^([a-zA-Z-]+)\[(.+)\]$`)
	matches := re.FindStringSubmatch(hostlist)
	if len(matches) != 3 {
		return false
	}
	prefix := matches[1]
	rangesStr := matches[2]

	// check for non-numeric part of the hostname
	if !strings.HasPrefix(hostname, prefix) {
		return false
	}

	hostNumStr := hostname[len(prefix):]
	hostNum, err := strconv.Atoi(hostNumStr)
	if err != nil {
		log.Printf("HostnameInList error: parsing hostname: %s, %s\n", hostname, err)
		return false
	}

	ranges := strings.Split(rangesStr, ",")
	for _, r := range ranges {
		if strings.Contains(r, "-") {
			bounds := strings.Split(r, "-")
			start, err := strconv.Atoi(bounds[0])
			if err != nil {
				log.Printf("HostnameInList error: parsing hostlist range start: %s, %s\n", r, err)
				return false
			}
			end, err := strconv.Atoi(bounds[1])
			if err != nil {
				log.Printf("HostnameInList error: parsing hostlist range end: %s, %s\n", r, err)
				return false
			}
			if hostNum >= start && hostNum <= end {
				return true
			}
		} else {
			index, err := strconv.Atoi(r)
			if err != nil {
				log.Printf("HostnameInList error: parsing hostlist number: %s, %s\n", r, err)
				return false
			}
			if hostNum == index {
				return true
			}
		}
	}
	// if no match was found
	return false
}
