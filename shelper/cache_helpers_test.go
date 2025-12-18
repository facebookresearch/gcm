// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestValidCacheGetSlurmMetadataCache(t *testing.T) {
	cacheFile, err := os.CreateTemp("", "slurm_metadata_cache")
	if err != nil {
		t.Fatal(err)
	}
	defer func() {
		if err := os.Remove(cacheFile.Name()); err != nil {
			t.Fatal(err)
		}
	}()
	testData := "test data"
	err = os.WriteFile(cacheFile.Name(), []byte(testData), 0644)
	if err != nil {
		t.Fatal(err)
	}
	cacheDuration := 10000
	cachedData, err := GetSlurmMetadataCache(cacheFile.Name(), cacheDuration)
	if err != nil {
		t.Fatal(err)
	}

	assert.Equal(t, cachedData, testData)
}

func TestInvalidCacheGetSlurmMetadataCache(t *testing.T) {
	cacheFile, err := os.CreateTemp("", "slurm_metadata_cache")
	if err != nil {
		t.Fatal(err)
	}
	defer func() {
		if err := os.Remove(cacheFile.Name()); err != nil {
			t.Fatal(err)
		}
	}()
	testData := "test data"
	err = os.WriteFile(cacheFile.Name(), []byte(testData), 0644)
	if err != nil {
		t.Fatal(err)
	}
	cacheDuration := 0
	cachedData, _ := GetSlurmMetadataCache(cacheFile.Name(), cacheDuration)
	assert.Equal(t, cachedData, "")
}
