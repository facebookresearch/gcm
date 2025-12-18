# check-authentication

Authentication and user access validation checks for verifying password status and file system permissions.

## Available Health Checks

| Check | Purpose | Key Feature |
|-------|---------|-------------|
| [check-path-access-by-user](./check-path-access-by-user.md) | File system access validation | Verifies read/write permissions for specific users |
| [password-status](./password-status.md) | Password configuration check | Validates password status using `passwd -S` |

## Quick Start

```shell
# Check if root can write to /tmp
health_checks check-authentication check-path-access-by-user --path /tmp [CLUSTER] app

# Verify root password is set
health_checks check-authentication password-status [CLUSTER] app

# Check specific user access
health_checks check-authentication check-path-access-by-user \
  --user appuser \
  --path /var/log/app.log \
  --operation read \
  [CLUSTER] \
  app
```
