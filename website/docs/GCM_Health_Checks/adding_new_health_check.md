---
sidebar_position: 5
---

# Adding New Health Check

Writing a new health-check follows the example outlined [in the deep dive](health_checks_deep_dive.md).
Let's assume that you write a check called `check_test`. The first step is to create your new check file `health_checks/checks/check_test.py`.

Next, define your check command inside this file, add it to the [`gcm/health_checks/checks/__init__.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/checks/__init__.py), and include it in the [`gcm/health_checks/cli/health_checks.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/cli/health_checks.py).

After that you can use the same boiler plate code as outlined [before](health_checks_deep_dive.md#health-check-boiler-plate-code) and add the core functionality of your check.
Do not forget to [test](#how-to-test-a-new-health-check) your check before submitting your PR.

Finally update the [README.md](health_checks/README.md) file with information about the newly added check.
