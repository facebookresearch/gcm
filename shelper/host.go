// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"os"
	"strings"
)

// GetHostname retrieves the current hostname
func GetHostname() (string, error) {
	hostname, err := os.Hostname()
	if err != nil {
		return "", err
	}
	dotIdx := strings.Index(hostname, ".")
	if dotIdx == -1 {
		return hostname, nil
	}
	filteredHostname := hostname[:dotIdx]
	return filteredHostname, nil
}
