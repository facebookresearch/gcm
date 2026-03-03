// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

// GetSlurmMetadataCache returns the cached result if it exists and is still valid, otherwise returns an empty string
func GetSlurmMetadataCache(cacheFilepath string, cacheDuration int) (string, error) {
	if _, err := os.Stat(cacheFilepath); os.IsNotExist(err) {
		return "", nil
	}

	fileMetadata, err := os.Stat(cacheFilepath)
	if err != nil {
		return "", err
	}

	if time.Since(fileMetadata.ModTime()).Seconds() > float64(cacheDuration) {
		return "", nil
	}

	cachedData, err := os.ReadFile(cacheFilepath)
	if err != nil {
		return "", err
	}

	return string(cachedData), nil
}

// SaveSlurmToJSON saves the slurm metadata to a JSON file
func SaveSlurmToJSON(cacheFilepath string, slurmMetadata map[string]SlurmMetadata) error {
	jsonData, err := json.Marshal(slurmMetadata)
	if err != nil {
		return err
	}

	dir := filepath.Dir(cacheFilepath)

	err = os.MkdirAll(dir, 0600)
	if err != nil {
		return err
	}

	err = os.WriteFile(cacheFilepath, jsonData, 0600)
	if err != nil {
		return err
	}

	return nil
}
