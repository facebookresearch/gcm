// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package shelper

// MetadataSource constants represent the different sources for GPU to Slurm metadata
type MetadataSource string

const (
	// Nvml uses NVML for metadata
	Nvml MetadataSource = "nvml"
	// Slurmd uses Slurm without querying slurmctld
	Slurmd MetadataSource = "slurmd"
	// SlurmCtld uses Slurm with querying slurmctld
	SlurmCtld MetadataSource = "slurmctld"
)

// Config Structure
type Config struct {
	// The metadata source to use ("nvml", "slurmd", or "slurmctld")
	Source MetadataSource `mapstructure:"metadata_source"`

	// The number of seconds to cache the results for Slurm calls in memory
	// CacheDuration affects the number of misattributed Slurm metadata at the beginning and end of the job lifetime for at most cache_duration seconds
	// Only relevant when Source is SlurmCtld
	CacheDuration int `mapstructure:"cache_duration"`

	// Path to the file where we'll cache the results for Slurm calls
	// Only relevant when Source is SlurmCtld
	CacheFilepath string `mapstructure:"cache_filepath"`

	// T234205156 (jakobjohnson)
	// Legacy field for backward compatibility
	// This field is used to determine the Source when it's not explicitly set
	QuerySlurmCtld bool `mapstructure:"query_slurmctld"`
}

// GetMetadataSource returns the metadata source based on the config
// This handles both the new Source field and the legacy QuerySlurmCtld field
func (c *Config) GetMetadataSource() MetadataSource {
	// If Source is explicitly set, use it
	if c.Source != "" {
		return c.Source
	}

	// Otherwise, determine source from legacy field
	if c.QuerySlurmCtld {
		return SlurmCtld
	}
	return Slurmd
}

// GetCacheDuration returns the cache duration
// This is a convenience method to make it clear that CacheDuration is only relevant for SlurmCtld
func (c *Config) GetCacheDuration() int {
	if c.GetMetadataSource() == SlurmCtld {
		return c.CacheDuration
	}
	return 0 // Not used in other modes
}

// GetCacheFilepath returns the cache filepath
// This is a convenience method to make it clear that CacheFilepath is only relevant for SlurmCtld
func (c *Config) GetCacheFilepath() string {
	if c.GetMetadataSource() == SlurmCtld {
		return c.CacheFilepath
	}
	return "" // Not used in other modes
}
