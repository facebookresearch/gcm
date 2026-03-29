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
		name     string
		hostname string
		hostlist string
		expected bool
	}{
		// Simple hostnames (letter-only prefix)
		{"simple exact match", "node1", "node1", true},
		{"simple bracket range", "node1", "node[0-2]", true},
		{"simple bracket range start", "node1", "node[1-2]", true},
		{"simple bracket mixed", "node3", "node[0-1,3-4]", true},
		{"simple bracket individual and range", "node3", "node[0-1,3,5-6]", true},
		{"simple bracket range end", "node6", "node[0-1,3,5-6]", true},
		{"simple not in range", "node1", "node[2-10]", false},
		{"simple gap in range", "node2", "node[0-1,3-4]", false},
		{"simple not in individual or range", "node4", "node[0-1,3,5-6]", false},
		{"simple above range", "node7", "node[0-1,3,5-6]", false},

		// Empty inputs
		{"both empty", "", "", false},
		{"empty hostname", "", "node1", false},
		{"empty hostlist", "node1", "", false},

		// CoreWeave hostnames (digits in prefix)
		{"cw single node exact", "cw-h100-214-045", "cw-h100-214-045", true},
		{"cw single node mismatch", "cw-h100-214-046", "cw-h100-214-045", false},
		{"cw comma-separated match first", "cw-h100-214-045", "cw-h100-214-045,cw-h100-220-049", true},
		{"cw comma-separated match second", "cw-h100-220-049", "cw-h100-214-045,cw-h100-220-049", true},
		{"cw comma-separated no match", "cw-h100-211-001", "cw-h100-214-045,cw-h100-220-049", false},
		{"cw bracket range match", "cw-h100-192-021", "cw-h100-192-[021,023,025,029]", true},
		{"cw bracket range no match", "cw-h100-192-022", "cw-h100-192-[021,023,025,029]", false},
		{"cw bracket range hyphen match", "cw-h100-192-023", "cw-h100-192-[021-025]", true},
		{"cw bracket range hyphen no match", "cw-h100-192-026", "cw-h100-192-[021-025]", false},
		{"cw multi-group match first", "cw-h100-192-023", "cw-h100-192-[021,023],cw-h100-193-[009,011]", true},
		{"cw multi-group match second", "cw-h100-193-009", "cw-h100-192-[021,023],cw-h100-193-[009,011]", true},
		{"cw multi-group no match", "cw-h100-194-001", "cw-h100-192-[021,023],cw-h100-193-[009,011]", false},
		{"cw multi-group wrong prefix", "cw-h100-192-009", "cw-h100-192-[021,023],cw-h100-193-[009,011]", false},

		// AWS hostnames (h200-test-NNN-NNN pattern)
		{"aws single node exact", "h200-test-003-019", "h200-test-003-019", true},
		{"aws single node mismatch", "h200-test-003-020", "h200-test-003-019", false},
		{"aws comma-separated match first", "h200-test-003-019", "h200-test-003-019,h200-test-007-084", true},
		{"aws comma-separated match second", "h200-test-007-084", "h200-test-003-019,h200-test-007-084", true},
		{"aws comma-separated no match", "h200-test-011-041", "h200-test-003-019,h200-test-007-084", false},
		{"aws bracket range match", "h200-test-003-019", "h200-test-003-[019,020]", true},
		{"aws bracket range no match", "h200-test-003-021", "h200-test-003-[019,020]", false},
		{"aws multi-group match", "h200-test-007-085", "h200-test-003-[019,020],h200-test-007-[084,085]", true},
		{"aws multi-group no match", "h200-test-011-041", "h200-test-003-[019,020],h200-test-007-[084,085]", false},
		{"aws hyphen range match", "h200-test-100-015", "h200-test-100-[010-020]", true},
		{"aws hyphen range no match", "h200-test-100-025", "h200-test-100-[010-020]", false},
		{"aws short name bracket", "h200-251-071", "h200-251-[071,072]", true},

		// Three-node comma-separated (no brackets)
		{"three nodes match middle", "node2", "node1,node2,node3", true},
		{"three nodes no match", "node4", "node1,node2,node3", false},

		// Mixed comma and bracket groups
		{"mixed plain and bracket match plain", "cw-h100-214-045", "cw-h100-214-045,cw-h100-192-[021,023]", true},
		{"mixed plain and bracket match bracket", "cw-h100-192-021", "cw-h100-214-045,cw-h100-192-[021,023]", true},
		{"mixed plain and bracket no match", "cw-h100-192-022", "cw-h100-214-045,cw-h100-192-[021,023]", false},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			result := HostnameInList(test.hostname, test.hostlist)
			assert.Equal(t, test.expected, result,
				"HostnameInList(%q, %q) = %v, want %v", test.hostname, test.hostlist, result, test.expected)
		})
	}
}

func TestSplitHostlistGroups(t *testing.T) {
	tests := []struct {
		name     string
		hostlist string
		expected []string
	}{
		{"single plain host", "node1", []string{"node1"}},
		{"two plain hosts", "node1,node2", []string{"node1", "node2"}},
		{"single bracket group", "node[1-3]", []string{"node[1-3]"}},
		{"bracket with commas inside", "cw-h100-192-[021,023,025]", []string{"cw-h100-192-[021,023,025]"}},
		{"two bracket groups", "cw-h100-192-[021,023],cw-h100-193-[009,011]", []string{"cw-h100-192-[021,023]", "cw-h100-193-[009,011]"}},
		{"plain and bracket mixed", "cw-h100-214-045,cw-h100-192-[021,023]", []string{"cw-h100-214-045", "cw-h100-192-[021,023]"}},
		{"three groups", "a-[1,2],b-003,c-[4-6]", []string{"a-[1,2]", "b-003", "c-[4-6]"}},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			result := splitHostlistGroups(test.hostlist)
			assert.Equal(t, test.expected, result)
		})
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
