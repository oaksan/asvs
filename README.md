# ASVS Self‑Assessment Tool

This repository implements a Spec‑Driven Development (SDD) based self‑assessment tool for OWASP ASVS 5.0.

---

## Docker Build Requirements

The project relies on **Docker Compose v2** for local development and testing. The `--build` flag uses **BuildKit** via the `docker-buildx` CLI plugin. To avoid runtime panics:

1. **Ensure a valid Buildx plugin** is installed:
   ```bash
   # Install the official Buildx binary (replace VERSION if needed)
   VERSION="v0.14.0"
   PLUGIN_URL="https://github.com/docker/buildx/releases/download/${VERSION}/buildx-${VERSION}.linux-amd64"
   curl -L "$PLUGIN_URL" -o ~/.docker/cli-plugins/docker-buildx
   chmod +x ~/.docker/cli-plugins/docker-buildx
   ```
2. **If Buildx cannot be installed**, you can fall back to the legacy Docker builder by disabling BuildKit:
   ```bash
   export COMPOSE_DOCKER_CLI_BUILD=0   # forces Compose to use the classic builder
   export DOCKER_BUILDKIT=0
   ```
3. **Diagnostic helper** – see `scripts/diagnose_buildx.sh` for an automated check that reports a missing or corrupted plugin.

### Why this matters
A corrupted or missing `docker-buildx` binary triggers the following panic when running `docker compose up --build`:
```
panic: slice bounds out of range [1:0]
```
This was observed in the project and fixed by removing the broken plugin and installing a correct version (see the SDD `SDD_DockerComposePanicFix.md`).

---

*For more details, refer to the Software Design Document:* [SDD_DockerComposePanicFix.md](../brain/a8d7b0c8-05c6-4565-945a-008e38660b6b/SDD_DockerComposePanicFix.md)

# asvs
