// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestParseNewLineToList(t *testing.T) {
	tests := []struct {
		input    string
		expected []string
	}{
		{"", []string{""}},
		{"1", []string{"1"}},
		{"1\n", []string{"1"}},
		{"1\n2", []string{"1", "2"}},
		{"1\n2\n", []string{"1", "2"}},
		{"1\n\n2", []string{"1", "", "2"}},
	}

	for _, test := range tests {
		assert := assert.New(t)

		result := parseNewLineToList(test.input)
		assert.Equal(test.expected, result)
	}
}

func TestGetGPUsFromEnv(t *testing.T) {
	tests := []struct {
		input    string
		expected []string
	}{
		{"SLURM_JOB_GPUS=1", []string{"1"}},
		{"SLURM_JOB_GPUS=1,2\x00", []string{"1", "2"}},
		{"SLURM_JOB_GPUS=1,2,\x00", []string{"1", "2"}},
		{"SLURM_JOB_GPUS=1,2 \x00", []string{"1", "2"}},
		{"SLURM_JOB_GPUS=1,2,3\x00SLURM_VAR=xyz", []string{"1", "2", "3"}},
		{"SLURM_VAR1=abc\x00SLURM_VAR2=xyz", []string{}},
		{"", []string{}},
		{"\x00", []string{}},
	}

	for _, test := range tests {
		assert := assert.New(t)

		result := getGPUsFromEnv(test.input)
		assert.Equal(test.expected, result)
	}
}
