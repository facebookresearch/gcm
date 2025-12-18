/* # Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.  */

/**
 * CUDA memory test program
 */

#include <cuda_runtime.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int bool;
#define true 1
#define false 0

#define DEFAULT_ALLOC_MEM_IN_GB 1
#define MAX_ALLOC_MEM_IN_GB 80

#define ALLOC_MEM_OPT_STR "alloc_mem_gb"

// extern __host__ cudaError_t CUDARTAPI cudaMemGetInfo(size_t *free, size_t
// *total);

int stringRemoveDelimiter(char delimiter, const char *string) {
  int string_start = 0;

  while (string[string_start] == delimiter) {
    string_start++;
  }

  if (string_start >= (int)strlen(string) - 1) {
    return 0;
  }

  return string_start;
}

bool checkCmdLineFlag(const int argc, const char **argv,
                      const char *string_ref) {
  bool bFound = false;

  if (argc >= 1) {
    int i;
    for (i = 1; i < argc; i++) {
      int string_start = stringRemoveDelimiter('-', argv[i]);
      const char *string_argv = &argv[i][string_start];

      const char *equal_pos = strchr(string_argv, '=');
      int argv_length = (int)(equal_pos == 0 ? (int)strlen(string_argv)
                                             : equal_pos - string_argv);

      int length = (int)strlen(string_ref);

      if (length == argv_length &&
          !strncasecmp(string_argv, string_ref, length)) {
        bFound = true;
        continue;
      }
    }
  }

  return bFound;
}

int getCmdLineArgumentInt(const int argc, const char **argv,
                          const char *string_ref) {
  bool bFound = false;
  int value = -1;

  if (argc >= 1) {
    int i;
    for (i = 1; i < argc; i++) {
      int string_start = stringRemoveDelimiter('-', argv[i]);
      const char *string_argv = &argv[i][string_start];
      int length = (int)strlen(string_ref);

      if (!strncasecmp(string_argv, string_ref, length)) {
        if (length + 1 <= (int)strlen(string_argv)) {
          int auto_inc = (string_argv[length] == '=') ? 1 : 0;
          value = atoi(&string_argv[length + auto_inc]);
        } else {
          value = 0;
        }

        bFound = true;
        continue;
      }
    }
  }

  if (bFound) {
    return value;
  } else {
    return 0;
  }
}

int main(int argc, char **argv) {

  if (checkCmdLineFlag(argc, (const char **)argv, "help") ||
      checkCmdLineFlag(argc, (const char **)argv, "?")) {
    printf("A simple cuda memory testing tool\n");
    printf("Usage --device=n (n >= 0 for deviceID),\n");
    printf("      --%s=k (allocates k GB)\n", ALLOC_MEM_OPT_STR);
    return EXIT_SUCCESS;
  }

  int devID = 0;
  size_t alloc_mem_gb = DEFAULT_ALLOC_MEM_IN_GB;

  if (checkCmdLineFlag(argc, (const char **)argv, "device")) {
    devID = getCmdLineArgumentInt(argc, (const char **)argv, "device");
    cudaError_t ret = cudaSetDevice(devID);
    if (ret != cudaSuccess) {
      printf("Invalid device id or device already in use\n");
      return EXIT_FAILURE;
    }
  } else {
    printf("A simple cuda memory testing tool\n");
    printf("Usage --device=n (n >= 0 for deviceID)\n");
    printf("      --%s=k (allocates k GB)\n", ALLOC_MEM_OPT_STR);
    return EXIT_SUCCESS;
  }

  // Get total memory available
  size_t free_memory, total_memory;

  cudaError_t ret = cudaMemGetInfo(&free_memory, &total_memory);
  if (ret == cudaSuccess) {
    printf("free mem %ld total mem %ld \n", free_memory, total_memory);
  }

  size_t requested_size = DEFAULT_ALLOC_MEM_IN_GB * 1000 * 1000 * 1000;
  if (checkCmdLineFlag(argc, (const char **)argv, ALLOC_MEM_OPT_STR)) {
    alloc_mem_gb =
        getCmdLineArgumentInt(argc, (const char **)argv, ALLOC_MEM_OPT_STR);
    printf("alloc %ld \n", alloc_mem_gb);
    if ((alloc_mem_gb == 0)) {
      alloc_mem_gb = DEFAULT_ALLOC_MEM_IN_GB;
    }
    requested_size = alloc_mem_gb * 1000 * 1000 * 1000;
  }
  // As usually cudaAlloc fails for requested sizes close to available/free
  // memory we will set max at 90% of free memory.
  size_t max_alloc_size = free_memory - (size_t)(0.1 * free_memory);
  // if ((alloc_mem_gb == 0) || (alloc_mem_gb > MAX_ALLOC_MEM_IN_GB)) {
  if (requested_size > max_alloc_size) {
    printf("Invalid allocation amount specified, using %lu\n", max_alloc_size);
    requested_size = max_alloc_size;
  }

  // Error code to check return values for CUDA calls
  // cudaError_t err = cudaSuccess;

  /*
  printf("size %ld \n",alloc_mem_gb);
  size_t size = alloc_mem_gb * 1000 * 1000 * 1000;
  size = free_memory-20000000;
  printf("size requested %ld\n", size);
  */

  unsigned int *d_A = NULL;
  cudaError_t err = cudaMalloc((void **)&d_A, requested_size);

  if (err != cudaSuccess) {
    fprintf(stderr, "Test failed (error code %s)!\n", cudaGetErrorString(err));
    return EXIT_FAILURE;
  }

  // Set the allocated memory to 0xf
  err = cudaMemset(d_A, 0xf, requested_size);
  if (err != cudaSuccess) {
    fprintf(stderr, "Test failed in setting mem(error code %s)!\n",
            cudaGetErrorString(err));
    return EXIT_FAILURE;
  }

  // Free device global memory
  err = cudaFree(d_A);

  if (err != cudaSuccess) {
    fprintf(stderr, "Failed to free device vector A (error code %s)!\n",
            cudaGetErrorString(err));
    return EXIT_FAILURE;
  }

  printf("CUDA memory test PASSED\n");
  return EXIT_SUCCESS;
}
