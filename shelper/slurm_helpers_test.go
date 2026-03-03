// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"os"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestGetSlurmDataFromSlurmLineAllGpus(t *testing.T) {
	content, err := os.ReadFile("./testdata/scontrol_out_all_gpus.txt")
	if err != nil {
		panic("Error opening testdata!")
	}
	blocks := strings.Split(string(content), "\n\n")

	GPU2Slurm := make(map[string]SlurmMetadata)
	expectedGPU2Slurm := map[string]SlurmMetadata{
		"0": {
			User:        "test_username",
			JobName:     "demo_ods",
			QOS:         "normal",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"1": {
			User:        "test_username",
			JobName:     "demo_ods",
			QOS:         "normal",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"2": {
			User:        "test_username",
			JobName:     "demo_ods",
			QOS:         "normal",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"3": {
			User:        "test_username",
			JobName:     "demo_ods",
			QOS:         "normal",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"4": {
			User:        "test_username",
			JobName:     "demo_ods",
			QOS:         "normal",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"5": {
			User:        "test_username",
			JobName:     "demo_ods",
			QOS:         "normal",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"6": {
			User:        "test_username",
			JobName:     "demo_ods",
			QOS:         "normal",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"7": {
			User:        "test_username",
			JobName:     "demo_ods",
			QOS:         "normal",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
	}

	AttributeGPU2SlurmMetadata(blocks, "node1751", GPU2Slurm)

	assert.Equal(t, GPU2Slurm, expectedGPU2Slurm, "Error attributing gpu data to slurm metadata")
}

func TestGetSlurmDataFromSlurmLineSomeGpus(t *testing.T) {
	content, err := os.ReadFile("./testdata/scontrol_out_some_gpus.txt")
	if err != nil {
		panic("Error opening testdata!")
	}
	blocks := strings.Split(string(content), "\n\n")

	GPU2Slurm := make(map[string]SlurmMetadata)
	expectedGPU2Slurm := map[string]SlurmMetadata{
		"0": {
			User:        "test_username",
			JobName:     "demo_ods",
			QOS:         "normal",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"1": {
			User:        "test_username",
			JobName:     "demo_ods",
			QOS:         "normal",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"2": {
			User:        "test_username",
			JobName:     "demo_ods",
			QOS:         "normal",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"3": {
			User:        "test_username",
			JobName:     "demo_ods",
			QOS:         "normal",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
	}

	AttributeGPU2SlurmMetadata(blocks, "node1751", GPU2Slurm)

	assert.Equal(t, GPU2Slurm, expectedGPU2Slurm, "Error attributing gpu data to slurm metadata")
}

func TestGetSlurmDataFromSlurmLineNoGpus(t *testing.T) {
	content, err := os.ReadFile("./testdata/scontrol_out_no_gpus.txt")
	if err != nil {
		panic("Error opening testdata!")
	}
	blocks := strings.Split(string(content), "\n\n")

	GPU2Slurm := make(map[string]SlurmMetadata)
	expectedGPU2Slurm := map[string]SlurmMetadata{}

	AttributeGPU2SlurmMetadata(blocks, "node1751", GPU2Slurm)

	assert.Equal(t, GPU2Slurm, expectedGPU2Slurm, "Error attributing gpu data to slurm metadata")
}

func TestGetSlurmDataFromSlurmLineUniqueEntries(t *testing.T) {
	content, err := os.ReadFile("./testdata/scontrol_out_unique_entries.txt")
	if err != nil {
		panic("Error opening testdata!")
	}
	blocks := strings.Split(string(content), "\n\n")

	GPU2Slurm := make(map[string]SlurmMetadata)
	expectedGPU2Slurm := map[string]SlurmMetadata{
		"0": {
			User:        "test_username",
			QOS:         "normal",
			JobName:     "demo_ods",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test2_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"1": {
			User:        "test_username",
			QOS:         "normal",
			JobName:     "demo_ods",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test2_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"2": {
			User:        "test_username",
			QOS:         "normal",
			JobName:     "demo_ods",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test2_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"3": {
			User:        "test_username",
			QOS:         "normal",
			JobName:     "demo_ods",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "28",
			Account:     "test2_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"5": {
			User:        "test_username_2",
			QOS:         "dev",
			JobName:     "demo_ods2",
			JobID:       "31214",
			ArrayJobID:  "31185",
			ArrayTaskID: "128",
			Account:     "test_account",
			Partition:   "test",
			NumNodes:    "3",
		},
		"6": {
			User:        "test_username_2",
			QOS:         "dev",
			JobName:     "demo_ods2",
			JobID:       "31214",
			ArrayJobID:  "31185",
			ArrayTaskID: "128",
			Account:     "test_account",
			Partition:   "test",
			NumNodes:    "3",
		},
		"7": {
			User:        "test_username_2",
			QOS:         "dev",
			JobName:     "demo_ods2",
			JobID:       "31214",
			ArrayJobID:  "31185",
			ArrayTaskID: "128",
			Account:     "test_account",
			Partition:   "test",
			NumNodes:    "3",
		},
	}
	AttributeGPU2SlurmMetadata(blocks, "node1751", GPU2Slurm)

	assert.Equal(t, GPU2Slurm, expectedGPU2Slurm, "Error attributing gpu data to slurm metadata")
}

func TestGetSlurmDataFromSlurmLineMainArrayJob(t *testing.T) {
	content, err := os.ReadFile("./testdata/scontrol_out_main_array_job.txt")
	if err != nil {
		panic("Error opening testdata!")
	}
	blocks := strings.Split(string(content), "\n\n")

	GPU2Slurm := make(map[string]SlurmMetadata)
	expectedGPU2Slurm := map[string]SlurmMetadata{
		"0": {
			User:        "test_username",
			QOS:         "normal",
			JobName:     "demo_ods",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "",
			Account:     "test2_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"1": {
			User:        "test_username",
			QOS:         "normal",
			JobName:     "demo_ods",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "",
			Account:     "test2_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"2": {
			User:        "test_username",
			QOS:         "normal",
			JobName:     "demo_ods",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "",
			Account:     "test2_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"3": {
			User:        "test_username",
			QOS:         "normal",
			JobName:     "demo_ods",
			JobID:       "30214",
			ArrayJobID:  "30185",
			ArrayTaskID: "",
			Account:     "test2_account",
			Partition:   "learn",
			NumNodes:    "1",
		},
		"5": {
			User:        "test_username_2",
			QOS:         "dev",
			JobName:     "demo_ods2",
			JobID:       "31214",
			ArrayJobID:  "31185",
			ArrayTaskID: "128",
			Account:     "test_account",
			Partition:   "test",
			NumNodes:    "3",
		},
		"6": {
			User:        "test_username_2",
			QOS:         "dev",
			JobName:     "demo_ods2",
			JobID:       "31214",
			ArrayJobID:  "31185",
			ArrayTaskID: "128",
			Account:     "test_account",
			Partition:   "test",
			NumNodes:    "3",
		},
		"7": {
			User:        "test_username_2",
			QOS:         "dev",
			JobName:     "demo_ods2",
			JobID:       "31214",
			ArrayJobID:  "31185",
			ArrayTaskID: "128",
			Account:     "test_account",
			Partition:   "test",
			NumNodes:    "3",
		},
	}
	AttributeGPU2SlurmMetadata(blocks, "node1751", GPU2Slurm)

	assert.Equal(t, GPU2Slurm, expectedGPU2Slurm, "Error attributing gpu data to slurm metadata")
}

func TestParseGRES(t *testing.T) {
	tests := []struct {
		input    string
		expected []string
	}{
		{"gpu:ampere:1(IDX:0-1,3-4,6-7)", []string{"0", "1", "3", "4", "6", "7"}},
		{"gpu:ampere:1(IDX:0,2-3,5)", []string{"0", "2", "3", "5"}},
		{"gpu:ampere:1(IDX:0-2,4,5-7)", []string{"0", "1", "2", "4", "5", "6", "7"}},
		{"gpu:ampere:1(IDX:0,2-3)", []string{"0", "2", "3"}},
		{"gpu:ampere:1(IDX:0,2,4)", []string{"0", "2", "4"}},
		{"gpu:ampere:1(IDX:1-3)", []string{"1", "2", "3"}},
		{"gpu:ampere:1(IDX:)", []string{}},
		{"", []string{}},
		{"malformed string", []string{}},
	}

	for _, test := range tests {
		assert := assert.New(t)

		result := parseGRES(test.input)
		assert.Equal(test.expected, result)
	}
}

func TestHostnameInList(t *testing.T) {
	tests := []struct {
		hostname string
		hostlist string
		expected bool
	}{
		{"node1", "node1", true},
		{"node1", "node[0-2]", true},
		{"node1", "node[1-2]", true},
		{"node3", "node[0-1,3-4]", true},
		{"node3", "node[0-1,3,5-6]", true},
		{"node6", "node[0-1,3,5-6]", true},
		{"node1", "node[2-10]", false},
		{"node2", "node[0-1,3-4]", false},
		{"node4", "node[0-1,3,5-6]", false},
		{"node7", "node[0-1,3,5-6]", false},
		{"", "", false},
	}

	for _, test := range tests {
		assert := assert.New(t)

		result := HostnameInList(test.hostname, test.hostlist)
		assert.Equal(test.expected, result)
	}
}

func TestGetHostList(t *testing.T) {
	testCases := []struct {
		name     string
		filepath string
		expected string
	}{
		{
			filepath: "./testdata/scontrol_out_all_gpus.txt",
			expected: "node1751",
		},
		{
			filepath: "./testdata/scontrol_out_main_array_job.txt",
			expected: "node1751",
		},
		{
			filepath: "./testdata/scontrol_out_multi_node.txt",
			expected: "node[1433,1787,1795,1854,1889-1890,1968-1969]",
		},
		{
			filepath: "./testdata/scontrol_out_no_gpus.txt",
			expected: "node1751",
		},
		{
			filepath: "./testdata/scontrol_out_repeated_entry.txt",
			expected: "node1751",
		},
		{
			filepath: "./testdata/scontrol_out_some_gpus.txt",
			expected: "node1751",
		},
		{
			filepath: "./testdata/scontrol_out_unique_entries.txt",
			expected: "node1751",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {

			content, err := os.ReadFile(tc.filepath)
			if err != nil {
				panic("Error opening testdata!")
			}

			host := GetHostList(string(content))
			assert.Equal(t, host, tc.expected, "Error getting NodeList from scontrol")

		})
	}
}

func TestGetGPUData(t *testing.T) {
	GPUToSlurm := map[string]SlurmMetadata{
		"0": {
			JobID:       "123",
			JobName:     "test_job_gpu-0",
			QOS:         "normal",
			User:        "user1",
			Partition:   "test_partition",
			Account:     "test_account",
			NumNodes:    "1",
			ArrayJobID:  "0",
			ArrayTaskID: "0",
		},
		"1": {
			JobID:       "1234",
			JobName:     "test_job_gpu-1",
			QOS:         "dev",
			User:        "user2",
			Partition:   "test_partition",
			Account:     "test_account",
			NumNodes:    "1",
			ArrayJobID:  "10",
			ArrayTaskID: "10",
		},
	}
	expectedMetadata := SlurmMetadataList{
		JobID:       []string{"123", "1234"},
		JobName:     []string{"test_job_gpu-0", "test_job_gpu-1"},
		QOS:         []string{"dev", "normal"},
		User:        []string{"user1", "user2"},
		Partition:   []string{"test_partition"},
		Account:     []string{"test_account"},
		NumNodes:    []string{"1"},
		ArrayJobID:  []string{"0", "10"},
		ArrayTaskID: []string{"0", "10"},
	}

	metadata := GetGPUData(GPUToSlurm)
	assert := assert.New(t)
	assert.Equal(expectedMetadata, metadata)
}
