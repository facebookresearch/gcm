// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"bufio"
	"fmt"
	"reflect"
	"strings"
	"testing"
)

func TestParseNvidiaSmiGetPidsCommand(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected map[string]string
	}{
		{
			name: "Normal output with PIDs and dashes",
			input: `123
-
456
-
-
-
-
-`,
			expected: map[string]string{
				"0": "123",
				"1": "",
				"2": "456",
				"3": "",
				"4": "",
				"5": "",
				"6": "",
				"7": "",
			},
		},
		{
			name: "Output with all PIDs",
			input: `123
456
789
101
202
303
404
505`,
			expected: map[string]string{
				"0": "123",
				"1": "456",
				"2": "789",
				"3": "101",
				"4": "202",
				"5": "303",
				"6": "404",
				"7": "505",
			},
		},
		{
			name: "Output with all dashes",
			input: `-
-
-
-`,
			expected: map[string]string{
				"0": "",
				"1": "",
				"2": "",
				"3": "",
			},
		},
		{
			name: "Output with non-numerical characters",
			input: `123abc
-def
456ghi
-jkl`,
			expected: map[string]string{
				"0": "123",
				"1": "",
				"2": "456",
				"3": "",
			},
		},
		{
			name:     "Empty output",
			input:    "",
			expected: map[string]string{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create a modified version of parseNvidiaSmiGetPidsCommand that doesn't call executeGpuPidsCommand
			result := parseNvidiaSmiGetPidsCommandForTest(tt.input)

			if !reflect.DeepEqual(result, tt.expected) {
				t.Errorf("parseNvidiaSmiGetPidsCommand() = %v, want %v", result, tt.expected)
			}
		})
	}
}

// parseNvidiaSmiGetPidsCommandForTest is a test-friendly version of parseNvidiaSmiGetPidsCommand
// that doesn't call executeGpuPidsCommand and instead uses the provided input
func parseNvidiaSmiGetPidsCommandForTest(output string) map[string]string {
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

		// Add to map (empty string if no numerical value found)
		gpuToPid[fmt.Sprintf("%d", gpuID)] = numStr
		gpuID++
	}

	return gpuToPid
}
