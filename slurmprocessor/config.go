// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
package main

// Config Structure
type Config struct {
	// The number of seconds to cache the results for Slurm calls in memory
	// CacheDuration affects the number of misattributed Slurm metadata at the beginning and end of the job lifetime for at most cache_duration seconds
	CacheDuration int `mapstructure:"cache_duration"`

	// Path to the file where we'll cache the results for Slurm calls
	CacheFilepath string `mapstructure:"cache_filepath"`

	// boolean that decides whether or not we'll query slurmctld
	QuerySlurmCtld bool `mapstructure:"query_slurmctld"`
}
