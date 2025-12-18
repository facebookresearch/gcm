<!--
Copyright (c) Meta Platforms, Inc. and affiliates.
All rights reserved.
-->
# Releasing a new version
We should release new versions periodically so that the latest changes in `main` can be deployed to production.

To release a new version:

1. Open a github PR that bumps the [version.txt](../version.txt) file to the new version.
1. Merge the PR to the main branch.
1. A new Github Release should be created from a Github CI job ([release.yml](../../.github/workflows/release.yml))

To build GCM from source, check out [Building the Debian package](./CONTRIBUTING.md#building-the-debian-package).
