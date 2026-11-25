---
name: gcp-ci
description: "GCP CI conventions: Artifact Registry image paths (never gcr.io), build service-account roles, docker auth. Load when writing cloudbuild.yaml or a Dockerfile push step, setting a Cloud Run or GKE image path, or fixing an image push denial."
applyTo: '**/cloudbuild.yaml,**/Dockerfile'
tags: [infra, standards]
---

# GCP CI Conventions

Platform rules for building and shipping containers on GCP, independent of the IaC
tool. Infra that consumes these images (Cloud Run, GKE, …) references them by the
Artifact Registry path below.

## Image Registry — Artifact Registry only

Publish container images to **Artifact Registry**, never the legacy Container
Registry (`gcr.io/…`, GCS-backed). `gcr.io` images don't appear under the Artifact
Registry repos teams browse, and Container Registry is deprecated. Convention:

```
<region>-docker.pkg.dev/<project>/<project>/<service>:<tag>
```

- **Repository = the project name** — one Docker repo per project, in the stack's
  `gcp:region`. Create it once if absent:
  ```bash
  gcloud artifacts repositories create <project> --repository-format=docker \
    --location=<region> --project=<project>
  ```
- **Image = the service name** (`api`, `web`, `report`, …); the build tag versions
  it (use a unique, commit-traceable tag like `<short-sha>-<UTC-timestamp>`, and
  `:latest`).
- Reference this **full path everywhere** — Cloud Run/GKE manifests, IaC config,
  and every build pipeline. Never mix `gcr.io` and `pkg.dev` for the same service.

## Pushing — permissions & auth

- The pusher (Cloud Build SA, GitHub Actions WIF SA, or you locally) needs
  **`roles/artifactregistry.writer`** on the project (or the repo).
- Local docker must register the AR credential helper once:
  ```bash
  gcloud auth configure-docker <region>-docker.pkg.dev
  ```

## Per-service build pipeline

Each service owns a `cloudbuild.yaml` that builds + tags + pushes only its image;
deployment is a separate step (bump the tag in the IaC config, then run the deploy
pipeline). A minimal build config:

```yaml
substitutions:
  _IMAGE: <region>-docker.pkg.dev/<project>/<project>/<service>
  _TAG: latest
steps:
  - name: gcr.io/cloud-builders/docker   # builder image; output goes to Artifact Registry
    args: ["build", "-t", "${_IMAGE}:${_TAG}", "-t", "${_IMAGE}:latest", "."]
images:
  - "${_IMAGE}:${_TAG}"
  - "${_IMAGE}:latest"
options:
  logging: CLOUD_LOGGING_ONLY
```

Trigger it from the service's own Makefile (compute the tag, pass `_TAG`, print it
back), or from a Cloud Build trigger scoped with `includedFiles: ["<service>/**"]`.
The `images:` field is what performs the push.

