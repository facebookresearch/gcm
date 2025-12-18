// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestConfigMetadataSources(t *testing.T) {
	// Test case 1: Explicit Source setting
	cfg1 := &Config{
		Source:         Nvml,
		CacheDuration:  60,
		CacheFilepath:  "/tmp/cache.json",
		QuerySlurmCtld: true, // This should be ignored since Source is explicitly set
	}
	assert.Equal(t, Nvml, cfg1.GetMetadataSource())
	assert.True(t, cfg1.GetMetadataSource() == Nvml)
	assert.False(t, cfg1.GetMetadataSource() == SlurmCtld)
	assert.Equal(t, 0, cfg1.GetCacheDuration())  // Should be 0 since Nvml doesn't use cache
	assert.Equal(t, "", cfg1.GetCacheFilepath()) // Should be empty since Nvml doesn't use cache

	// Test case 2: Legacy field - QuerySlurmCtld=true
	cfg2 := &Config{
		CacheDuration:  120,
		CacheFilepath:  "/tmp/cache2.json",
		QuerySlurmCtld: true,
	}
	assert.Equal(t, SlurmCtld, cfg2.GetMetadataSource())
	assert.False(t, cfg2.GetMetadataSource() == Nvml)
	assert.True(t, cfg2.GetMetadataSource() == SlurmCtld)
	assert.Equal(t, 120, cfg2.GetCacheDuration())
	assert.Equal(t, "/tmp/cache2.json", cfg2.GetCacheFilepath())

	// Test case 3: Legacy field - QuerySlurmCtld=false
	cfg3 := &Config{
		CacheDuration:  60,
		CacheFilepath:  "/tmp/cache.json",
		QuerySlurmCtld: false,
	}
	assert.Equal(t, Slurmd, cfg3.GetMetadataSource())
	assert.False(t, cfg3.GetMetadataSource() == Nvml)
	assert.False(t, cfg3.GetMetadataSource() == SlurmCtld)
	assert.Equal(t, 0, cfg3.GetCacheDuration())  // Should be 0 since Slurmd doesn't use cache
	assert.Equal(t, "", cfg3.GetCacheFilepath()) // Should be empty since Slurmd doesn't use cache
}
