---
name: pulumi-ci-docker
description: "Pulumi deploy CI on Cloud Build: Pulumi Docker image, cloudbuild.yaml, .gcloudignore, build service-account roles, stuck stack recovery. Load when editing cloudbuild.yaml, the Pulumi Dockerfile or .gcloudignore, or unlocking a stack."
applyTo: '{{ template.pulumi_path | default("pulumi") }}/cloudbuild.yaml,{{ template.pulumi_path | default("pulumi") }}/Dockerfile,{{ template.pulumi_path | default("pulumi") }}/.gcloudignore'
tags: [pulumi, infra, standards]
---

# Pulumi Deploy CI (Cloud Build + custom Pulumi image)

Apply Pulumi stacks through a **Cloud Build pipeline**, not by running `pulumi up`
from a workstation. A local run that is interrupted (wall-clock timeout, Ctrl-C)
leaves a **state lock + "pending operations"** that poison the next run; the CI
runs in a clean, consistent environment with the deploy service account's
permissions. This skill is the CI/Docker subset of the
{{ skill_path("pulumi") }} skill — read that for state backend, the empty
passphrase, secret vs. env, and the config-driven app layout.

## 1. Custom Pulumi CI Docker image

Bake the Pulumi CLI, the **provider plugins**, and `node_modules` into an image so
every deploy reuses them instead of reinstalling. `{{ template.pulumi_path | default("pulumi") }}/Dockerfile`:

```dockerfile
FROM node:22-alpine3.21
RUN apk add --no-cache curl bash && curl -fsSL https://get.pulumi.com | sh && \
    /root/.pulumi/bin/pulumi plugin install resource gcp <gcp-plugin-version>
WORKDIR /app
ENV PATH="/root/.pulumi/bin:${PATH}"
COPY package.json package-lock.json tsconfig.json /app/
RUN npm ci
ENTRYPOINT ["/bin/bash"]
```

- Pin `<gcp-plugin-version>` to the **`@pulumi/gcp` version in `package.json`** so
  the baked plugin matches the program (mismatch → plugin re-download at runtime).
- Build & push when deps or plugins change (Artifact Registry — see the registry
  rule in {{ skill_path("pulumi") }}):
  ```bash
  docker build -t <region>-docker.pkg.dev/<project>/<project>/pulumi-ci:<tag> {{ template.pulumi_path | default("pulumi") }}
  docker push <region>-docker.pkg.dev/<project>/<project>/pulumi-ci:<tag>
  ```

## 2. The cloudbuild.yaml

`{{ template.pulumi_path | default("pulumi") }}/cloudbuild.yaml` reuses that image and **symlinks** the baked deps instead of `npm ci`:

```yaml
substitutions:
  _PULUMI_STATE_BUCKET: {{ template.pulumi_project | default("example") }}-pulumi-state
  _PULUMI_STACK: prod
  _PULUMI_CI_IMAGE: <region>-docker.pkg.dev/{{ template.pulumi_project | default("example") }}/{{ template.pulumi_project | default("example") }}/pulumi-ci:1.0.0
steps:
  - name: "${_PULUMI_CI_IMAGE}"
    entrypoint: sh
    args:
      - -ceux
      - |
        export PULUMI_CONFIG_PASSPHRASE=''        # empty by convention
        pulumi login "gs://${_PULUMI_STATE_BUCKET}"
        cd {{ template.pulumi_path | default("pulumi") }}
        ln -s /app/node_modules "$(pwd)/node_modules"   # reuse baked deps
        pulumi stack select "${_PULUMI_STACK}"
        pulumi up --yes --skip-preview
timeout: 1800s
options:
  logging: CLOUD_LOGGING_ONLY
```

The CI builds **no app images** — those are pushed separately and referenced by
tag in `Pulumi.<stack>.yaml`. The pipeline only runs `pulumi up`.

## 3. How the repo reaches the build

`gcloud builds submit --config {{ template.pulumi_path | default("pulumi") }}/cloudbuild.yaml .` — the trailing `.` is the
source. gcloud **tars the current dir** (honoring `.gcloudignore`), uploads it to
`gs://<project>_cloudbuild/source/…`, and Cloud Build unpacks it into `/workspace`
(so the step's `cd {{ template.pulumi_path | default("pulumi") }}` is `/workspace/{{ template.pulumi_path | default("pulumi") }}`). It is a snapshot of the
**local working tree** — uncommitted edits included.

Add a **`.gcloudignore`** at the submit root or the tarball balloons:
```
.git
**/node_modules
# plus unrelated app dirs not needed by `pulumi up`
```

Production alternative: a **Cloud Build trigger** on push to the default branch
with `includedFiles: ["{{ template.pulumi_path | default("pulumi") }}/**"]` — sends the *committed* repo automatically.

## 4. Build service-account roles

With no `serviceAccount` on the build, the default Cloud Build SA
(`<project-number>@cloudbuild.gserviceaccount.com`) runs Pulumi. It needs to manage
the stack's resources. A Cloud Run + secrets + storage stack fails the first deploy
with `403 ... run.services.update denied`, `compute.regions.list forbidden`, or
`storage.buckets.getIamPolicy denied` until you grant (idempotent):

```bash
CB_SA="<project-number>@cloudbuild.gserviceaccount.com"
for R in roles/run.admin roles/iam.serviceAccountUser roles/secretmanager.admin \
         roles/artifactregistry.writer roles/storage.admin roles/compute.viewer; do
  gcloud projects add-iam-policy-binding <project> \
    --member="serviceAccount:$CB_SA" --role="$R" --condition=None
done
```
(`artifactregistry.writer` to push images; `storage.admin` covers GCS-backed
state/legacy buckets.)

`iam.serviceAccountUser` is required because Cloud Run services run *as* their own
per-service accounts — the deployer must act as them. Read a failed build with
`gcloud builds log <build-id>`; the 403 names the exact missing permission.

## 5. Recovering a stuck stack

- **Clear a lock from an interrupted run:** `PULUMI_CONFIG_PASSPHRASE="" pulumi cancel --yes`.
- **"N pending operations from previous deployment"** persists after `cancel`/`refresh`?
  Strip them via state surgery, then redeploy:
  ```bash
  export PULUMI_CONFIG_PASSPHRASE=""
  pulumi cancel --yes
  pulumi stack export --file /tmp/state.json
  # set deployment.pending_operations = [] in /tmp/state.json
  pulumi stack import --file /tmp/state.json
  ```
- **Deploys "hang"** = Pulumi waiting on a Cloud Run startup probe. The default TCP
  probe checks once at ~240s. Add a fast probe to the container so readiness (or
  failure) is detected in seconds:
  ```typescript
  startupProbe: { tcpSocket: { port }, periodSeconds: 5, timeoutSeconds: 4, failureThreshold: 30 }
  ```

## Verification

```bash
gcloud builds submit --config {{ template.pulumi_path | default("pulumi") }}/cloudbuild.yaml --project <project> .
gcloud builds list --project <project> --limit 1 --format='value(status)'   # expect SUCCESS
gcloud run services list --project <project>                                # ready revisions on new images
```

