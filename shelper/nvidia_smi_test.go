// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"errors"
	"reflect"
	"testing"
)

func TestParseNvidiaSmiGetPidsCommand(t *testing.T) {
	input := `# gpu pid type sm mem enc dec command
# Idx # C/G % % % % name
0 123 C 0 0 - - python
0 124 C 0 0 - - python
1 - - - - - - -
3 456 C 0 0 - - python
7 789 C 0 0 - - python
invalid output
2 123abc C 0 0 - - invalid
-1 999 C 0 0 - - invalid
2 0 C 0 0 - - invalid
`
	want := map[string][]string{"0": {"123", "124"}, "3": {"456"}, "7": {"789"}}
	if got := parseNvidiaSmiGetPidsCommand(input); !reflect.DeepEqual(got, want) {
		t.Fatalf("GPU process mapping = %v, want %v", got, want)
	}
	if got := parseNvidiaSmiGetPidsCommand(""); len(got) != 0 {
		t.Fatalf("empty output mapped to %v", got)
	}
}

func TestMetadataForGPU(t *testing.T) {
	job := SlurmMetadata{JobID: "42", JobName: "train=a", User: "alice", Account: "research", Partition: "gpu", QOS: "normal"}
	otherJob := job
	otherJob.JobID = "43"
	for _, tc := range []struct {
		name string
		pids []string
		want bool
	}{
		{"one process", []string{"1"}, true},
		{"multiple processes same job", []string{"1", "2"}, true},
		{"different jobs sharing GPU", []string{"1", "3"}, false},
		{"process without Slurm metadata", []string{"1", "4"}, false},
		{"process disappeared", []string{"1", "5"}, false},
		{"idle GPU", nil, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			got, ok := metadataForGPU(tc.pids, func(pid string) (SlurmMetadata, error) {
				switch pid {
				case "1", "2":
					return job, nil
				case "3":
					return otherJob, nil
				case "4":
					return SlurmMetadata{}, nil
				default:
					return SlurmMetadata{}, errors.New("process exited")
				}
			})
			if ok != tc.want || (ok && got != job) {
				t.Fatalf("metadata = %+v, attributed = %v; want attributed = %v", got, ok, tc.want)
			}
		})
	}
}

func TestProcEnvironmentValuesContainingEquals(t *testing.T) {
	env := "SLURM_JOB_ID=42\x00SLURM_JOB_NAME=train=a=b\x00MALFORMED\x00"
	if got := parseProcEnvStrToMap(env)["SLURM_JOB_NAME"]; got != "train=a=b" {
		t.Fatalf("job name = %q", got)
	}
	if got, err := parseVarFromProcEnvStr(env, "SLURM_JOB_NAME"); err != nil || got != "train=a=b" {
		t.Fatalf("job name = %q, error = %v", got, err)
	}
}
