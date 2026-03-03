// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"os"
	"path/filepath"
	"testing"
)

func TestParseVarFromProcEnvStr(t *testing.T) {
	tests := []struct {
		name        string
		env         string
		varName     string
		expected    string
		expectError bool
	}{
		{
			name:        "basic case",
			env:         "VAR1=value1\x00VAR2=value2\x00VAR3=value3\x00",
			varName:     "VAR2",
			expected:    "value2",
			expectError: false,
		},
		{
			name:        "variable not found",
			env:         "VAR1=value1\x00VAR2=value2\x00VAR3=value3\x00",
			varName:     "VAR4",
			expected:    "",
			expectError: true,
		},
		{
			name:        "empty environment",
			env:         "",
			varName:     "VAR1",
			expected:    "",
			expectError: true,
		},
		{
			name:        "malformed line",
			env:         "VAR1=value1\x00VAR2value2\x00VAR3=value3\x00",
			varName:     "VAR3",
			expected:    "value3",
			expectError: false,
		},
		{
			name:        "variable with empty value",
			env:         "VAR1=value1\x00VAR2=\x00VAR3=value3\x00",
			varName:     "VAR2",
			expected:    "",
			expectError: false,
		},
		{
			name:        "variable with special characters",
			env:         "VAR1=value1\x00PATH=/usr/bin:/usr/local/bin\x00VAR3=value3\x00",
			varName:     "PATH",
			expected:    "/usr/bin:/usr/local/bin",
			expectError: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			result, err := parseVarFromProcEnvStr(tc.env, tc.varName)

			if tc.expectError && err == nil {
				t.Errorf("Expected error but got none")
			}

			if !tc.expectError && err != nil {
				t.Errorf("Unexpected error: %v", err)
			}

			if result != tc.expected {
				t.Errorf("Expected %q but got %q", tc.expected, result)
			}
		})
	}
}

func TestDoesPIDExist(t *testing.T) {
	// Create a temporary directory to simulate proc fs
	tempDir, err := os.MkdirTemp("", "proc_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer func() {
		if err := os.RemoveAll(tempDir); err != nil {
			t.Fatal(err)
		}
	}()

	// Create a directory for an existing PID
	existingPID := "12345"
	err = os.Mkdir(filepath.Join(tempDir, existingPID), 0755)
	if err != nil {
		t.Fatalf("Failed to create PID directory: %v", err)
	}

	// Test cases
	tests := []struct {
		name     string
		pid      string
		procRoot string
		expected bool
	}{
		{
			name:     "existing PID",
			pid:      existingPID,
			procRoot: tempDir,
			expected: true,
		},
		{
			name:     "non-existing PID",
			pid:      "99999",
			procRoot: tempDir,
			expected: false,
		},
		{
			name:     "invalid proc root",
			pid:      existingPID,
			procRoot: "/non/existent/path",
			expected: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			result := doesPIDExist(tc.pid, tc.procRoot)
			if result != tc.expected {
				t.Errorf("Expected %v but got %v", tc.expected, result)
			}
		})
	}
}

func TestGetProcEnvStr(t *testing.T) {
	// Create a temporary directory to simulate proc fs
	tempDir, err := os.MkdirTemp("", "proc_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer func() {
		if err := os.RemoveAll(tempDir); err != nil {
			t.Fatal(err)
		}
	}()

	// Create directories and files for test cases
	// 1. PID with environ file
	pidWithEnv := "12345"
	pidDir := filepath.Join(tempDir, pidWithEnv)
	err = os.Mkdir(pidDir, 0755)
	if err != nil {
		t.Fatalf("Failed to create PID directory: %v", err)
	}

	environContent := "VAR1=value1\x00VAR2=value2\x00VAR3=value3\x00"
	err = os.WriteFile(filepath.Join(pidDir, "environ"), []byte(environContent), 0644)
	if err != nil {
		t.Fatalf("Failed to create environ file: %v", err)
	}

	// 2. PID without environ file
	pidWithoutEnv := "67890"
	err = os.Mkdir(filepath.Join(tempDir, pidWithoutEnv), 0755)
	if err != nil {
		t.Fatalf("Failed to create PID directory: %v", err)
	}

	// Test cases
	tests := []struct {
		name        string
		pid         string
		procRoot    string
		expected    string
		expectError bool
	}{
		{
			name:        "PID with environ file",
			pid:         pidWithEnv,
			procRoot:    tempDir,
			expected:    environContent,
			expectError: false,
		},
		{
			name:        "PID without environ file",
			pid:         pidWithoutEnv,
			procRoot:    tempDir,
			expected:    "",
			expectError: true,
		},
		{
			name:        "non-existing PID",
			pid:         "99999",
			procRoot:    tempDir,
			expected:    "",
			expectError: true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			result, err := getProcEnvStr(tc.pid, tc.procRoot)

			if tc.expectError && err == nil {
				t.Errorf("Expected error but got none")
			}

			if !tc.expectError && err != nil {
				t.Errorf("Unexpected error: %v", err)
			}

			if result != tc.expected {
				t.Errorf("Expected %q but got %q", tc.expected, result)
			}
		})
	}
}

func TestParseProcEnvStrToMap(t *testing.T) {
	tests := []struct {
		name     string
		env      string
		expected map[string]string
	}{
		{
			name: "basic case",
			env:  "VAR1=value1\x00VAR2=value2\x00VAR3=value3\x00",
			expected: map[string]string{
				"VAR1": "value1",
				"VAR2": "value2",
				"VAR3": "value3",
			},
		},
		{
			name:     "empty environment",
			env:      "",
			expected: map[string]string{},
		},
		{
			name: "with malformed line",
			env:  "VAR1=value1\x00VAR2value2\x00VAR3=value3\x00",
			expected: map[string]string{
				"VAR1": "value1",
				"VAR3": "value3",
			},
		},
		{
			name: "with empty values",
			env:  "VAR1=value1\x00VAR2=\x00VAR3=value3\x00",
			expected: map[string]string{
				"VAR1": "value1",
				"VAR2": "",
				"VAR3": "value3",
			},
		},
		{
			name: "with empty key",
			env:  "VAR1=value1\x00=empty_key\x00VAR3=value3\x00",
			expected: map[string]string{
				"VAR1": "value1",
				"":     "empty_key",
				"VAR3": "value3",
			},
		},
		{
			name: "with special characters",
			env:  "VAR1=value1\x00PATH=/usr/bin:/usr/local/bin\x00USER=root\x00",
			expected: map[string]string{
				"VAR1": "value1",
				"PATH": "/usr/bin:/usr/local/bin",
				"USER": "root",
			},
		},
		{
			name:     "without trailing null byte",
			env:      "VAR1=value1VAR2=value2\x00",
			expected: map[string]string{},
		},
		{
			name: "with empty string between null bytes",
			env:  "VAR1=value1\x00\x00VAR3=value3\x00",
			expected: map[string]string{
				"VAR1": "value1",
				"VAR3": "value3",
			},
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			result := parseProcEnvStrToMap(tc.env)

			if len(result) != len(tc.expected) {
				t.Errorf("Expected map of size %d but got %d", len(tc.expected), len(result))
			}

			for k, expectedVal := range tc.expected {
				if resultVal, ok := result[k]; !ok {
					t.Errorf("Expected key %q not found in result", k)
				} else if resultVal != expectedVal {
					t.Errorf("For key %q, expected %q but got %q", k, expectedVal, resultVal)
				}
			}
		})
	}
}
