---
name: pulumi
description: "Pulumi TypeScript on GCP: Cloud Build, Cloud Run, secrets vs env vars, IAM, Secret Manager, ComponentResource, aliases. Load when writing Pulumi TypeScript, adding a Cloud Run service or secret, renaming a resource, or running pulumi up."
applyTo: '{{ template.pulumi_path | default("pulumi") }}/**/*.ts'
tags: [pulumi, infra, standards, entrypoint]
---

# {{ template.infra_layer_name | default("Pulumi Infrastructure") }}

The infrastructure stack is managed with **{{ template.pulumi_language | default("Pulumi TypeScript") }}** targeting **{{ template.pulumi_provider_name | default("the configured cloud provider") }}**.

Primary managed services:

{{ template.pulumi_managed_services | default("- application runtime services\n- data stores\n- identity/auth services\n- object storage\n- secret management\n- CI/CD or deployment automation") }}

## State Backend & Secrets — read this BEFORE any pulumi command

Two fixed conventions for every stack in every environment. They are not optional
and never require human approval:

- **State lives in a Google Cloud Storage bucket** (self-managed backend) — never
  Pulumi Cloud, never the local filesystem. Log in to the bucket before any stack
  operation:
  ```bash
  pulumi login gs://{{ template.pulumi_project | default("example") }}-pulumi-state
  ```
  The bucket lives in the stack's GCP project (`gcp:project` in `Pulumi.<stack>.yaml`);
  the name convention is `<gcp-project>-pulumi-state`.

- **The passphrase is ALWAYS empty.** Export an empty passphrase for every pulumi
  command so it never prompts:
  ```bash
  export PULUMI_CONFIG_PASSPHRASE=""
  ```
  An empty/unset passphrase is the **expected** state, not a blocker. NEVER pause,
  declare work blocked, or ask a human to "supply `PULUMI_CONFIG_PASSPHRASE`" — it
  is empty by design. Set it to `""` and proceed.

- **Create the state bucket with gcloud if it does not exist.** A missing bucket is
  something to **create**, not a reason to stop:
  ```bash
  gcloud storage buckets create gs://<gcp-project>-pulumi-state \
    --project=<gcp-project> --location=<region> --uniform-bucket-level-access
  # older CLI: gsutil mb -p <gcp-project> -l <region> gs://<gcp-project>-pulumi-state
  ```
  Derive `<gcp-project>` and `<region>` from `gcp:project` / `gcp:region` in
  `Pulumi.<stack>.yaml`.

**Standard preamble for every Pulumi session:**
```bash
export PULUMI_CONFIG_PASSPHRASE=""
pulumi login gs://{{ template.pulumi_project | default("example") }}-pulumi-state   # create the bucket first if absent
cd {{ template.pulumi_path | default("pulumi") }} && pulumi stack select <stack>
```

## Deploy via Cloud Build CI — preferred over running `pulumi up` by hand

Apply stacks through a **Cloud Build pipeline that runs Pulumi** (with a prebuilt
custom Pulumi image), not by invoking `pulumi up` from a workstation — a local run
interrupted mid-flight leaves a lock + pending operations that poison the next run.
How to assemble the pipeline, the custom Docker image, the build service-account
roles, and how to recover a stuck stack are in the dedicated subset skill:
{{ skill_path("pulumi-ci-docker") }}.

## Image Registry

On GCP, container images **MUST** live in **Artifact Registry** under
`<region>-docker.pkg.dev/<project>/<project>/<service>:<tag>` — never `gcr.io`.
The full rule (repo = project, image = service), the push permissions, and the
per-service build pipeline are in {{ skill_path("gcp-ci") }}. Reference that
path everywhere — `cloudRunApps[].image`, the per-service build CIs, and the
{{ skill_path("pulumi-ci-docker") }} image.

## Artifact Registry — Cleanup Policies

Every `gcp.artifactregistry.Repository` that serves Pulumi-managed Cloud Run apps
**MUST** declare `cleanupPolicies` at creation. Never leave a Docker repo without
them — stale image versions accumulate indefinitely otherwise.

**Rules:**
- Set `cleanupPolicyDryRun: false` — dry-run mode silently skips deletions.
- **Always scope policies via `packageNamePrefixes`** to the `cloudRunApps[].name`
  values. Unscoped policies would affect untracked images in the same repo (e.g.
  static tooling images). Only touch what Pulumi knows about.
- Derive `packageNamePrefixes` from the `cloudRunApps` config object so new
  services are covered automatically on the next `pulumi up`.

**Standard policy set:** three policies, always all three: `keep-tagged`, `keep-recent-5` and
`delete-untagged-old`. Copy them from [references/cleanup-policies.md](references/cleanup-policies.md)
when creating or editing a repository.

KEEP policies take precedence over DELETE: a tagged or recent image is never
deleted even if it also matches the DELETE condition.

## Config-Driven Cloud Run Apps

Each runtime service is declared in `Pulumi.<stack>.yaml` under
`<project>:environment.cloudRunApps[]`, so every app is versioned and configured
independently (its own image, tag, port, scaling and env):

```yaml
{{ template.pulumi_project | default("example") }}:environment:
  cloudRunApps:
    - name: api
      image: <region>-docker.pkg.dev/{{ template.pulumi_project | default("example") }}/{{ template.pulumi_project | default("example") }}/api
      tag: <build-commit>          # bump to roll a new revision
      port: 8080
      vpcConnector: true
      envs:
        - name: STAGE
          value: prod
        # Non-secret runtime config (URLs, bucket names) belongs HERE as env
        # vars — NOT in secrets. A base URL is not a secret.
        - name: PUBLIC_BASE_URL
          value: https://...
    - name: web
      image: <region>-docker.pkg.dev/{{ template.pulumi_project | default("example") }}/{{ template.pulumi_project | default("example") }}/web
      tag: <build-commit>
      port: 8080
```

Keep `index.ts` resource names stable when moving to config-driven apps (reuse
the existing component type + logical name) so URNs don't change and resources
update in place.

## Secret vs. Env Var — classify every config value

**The test:** if leaking the value lets someone authenticate, decrypt, or sign,
it's a **secret**. If it only describes *where/how* the app runs (topology,
identifiers), it's an **env var**. A hostname, username, port, ID, URL, or bucket
name is **NOT a secret** — do not put it in Secret Manager.

| Goes in **`<project>:secrets`** (Secret Manager, encrypted, `secretKeyRef`) | Goes in **`cloudRunApps[].envs`** (plaintext) |
|---|---|
| DB **password** | DB **host, port, name, user** |
| API keys / tokens (Stripe, OpenAI, …) | Server **port**, `STAGE`, `LOG_LEVEL` |
| OAuth client secrets, webhook signing secrets | Project IDs, region |
| Private keys / service-account keys | Service **base URLs**, bucket names, feature flags |

Common mistakes to reject: `db-host`/`db-name`/`db-user` as secrets (they're
env), `server-port` as a secret (env), a base URL as a secret (env). Only the
**password/key/token** half of a connection is secret.

App side: read secrets from Secret Manager (or `secretKeyRef` env injection);
read non-secrets from plain env vars. In a reflection-based loader, tag secret
fields `secretmanager:"..."` and non-secret fields `env:"..."` — don't lump
config into Secret Manager just because it's adjacent to a credential.

### Writing a secret properly

Once you've confirmed a value *is* a secret (table above), never paste it
plaintext. The flow:

1. **Encrypt it into stack config.** Add it to the `<project>:secrets` list with
   `pulumi config set --secret` so it lands as a `secure:` ciphertext in
   `Pulumi.<stack>.yaml` (see [Secret Definitions](#secret-definitions)). Pipe the
   value from its source so it never prints to the terminal/logs:
   ```bash
   export PULUMI_CONFIG_PASSPHRASE=""
   pulumi config set --path "{{ template.pulumi_project | default("example") }}:secrets[0].name"  "db-password"
   gcloud secrets versions access latest --secret=prod-db-password \
     | pulumi config set --secret --path "{{ template.pulumi_project | default("example") }}:secrets[0].value"
   ```
   Result in `Pulumi.<stack>.yaml`: `value: { secure: v1:… }` — commit this; never
   a plaintext `value:`.
2. **Materialise it** — the program reads `requireSecretObject<SecretDefinition[]>("secrets")`
   and creates a `gcp.secretmanager.Secret` + `SecretVersion` per entry (ManagedSecret
   pattern). Match the existing Pulumi resource name (e.g. `_.camelCase(name)`) so
   renames don't replace the secret and destroy its versions.
3. **Grant + consume.** Grant the consuming service account
   `roles/secretmanager.secretAccessor` on the secret, then either read it from the
   Secret Manager API at boot, or inject it as a Cloud Run env via
   `valueFrom.secretKeyRef` (`cloudRunApps[].secretEnvs`). Have the service
   `dependsOn` the accessor binding (see Operational Gotchas).

> Caveat: with the empty passphrase (see State Backend & Secrets) a `secure:`
> value is decryptable by anyone who can read the file — it guards against casual
> exposure and plaintext-in-git, not a determined reader. Keep the repo and the
> `gs://<project>-pulumi-state` bucket access-controlled.

The Cloud Build deploy SA also needs `secretmanager.admin` to create/update these
secrets — see {{ skill_path("pulumi-ci-docker") }}.

## IAM

When granting IAM on shared GCP resources (secrets, buckets, …), default to the
additive `*IamMember`, not the authoritative `*IamBinding` — two authoritative
bindings on the same resource+role clobber each other and `PermissionDenied`
follows. The full rule, examples, and the Binding→Member migration are in
{{ skill_path("gcp-iam") }}.

## Operational Gotchas (Cloud Run + Secret Manager)

- **A new required secret crashes the app on the next deploy.** If the app reads
  config from Secret Manager at boot and you add a field whose secret doesn't
  exist, the access fails with **`PermissionDenied`** (GCP returns this, *not*
  `NotFound`, when the secret is absent and the caller lacks list rights). Loaders
  that only tolerate `NotFound` then hard-fail and the container exits. Create the
  secret (or move the field to a plain env var) **in the same change** that ships
  the code reading it.
- **App reads secrets at runtime, not via env injection?** Then the Cloud Run
  service has no Pulumi dependency on the secret, so order isn't guaranteed. Make
  the service `dependsOn` the secret-accessor IAM bindings so the SA can read them
  before the revision starts.
- **`pulumi up` "hangs" on a Cloud Run change** = it's waiting for the new
  revision to pass its startup probe (the default TCP probe can wait the full
  `periodSeconds`, often ~240s) before reporting Ready. A revision that crash-loops
  makes `pulumi up` block for minutes, then fail. Check
  `gcloud run revisions list --service <svc>` + the revision logs in parallel
  rather than assuming Pulumi is stuck.
- **Bump the image tag to roll a revision.** Cloud Run pins images by digest at
  deploy. Re-pushing the *same* tag doesn't change the Pulumi resource (the image
  string is unchanged) so no new revision deploys. Use a fresh tag per build.
- **Verify a refactor is in-place, not destructive.** Before applying a structural
  change, `pulumi preview` and confirm the summary shows `update`/`unchanged`, not
  `replace`/`delete`, for live infra (VPC connectors, egress IPs, populated
  secrets). `~ urn ...` lines are benign alias renames, not replacements.

## Project Structure

```
{{ template.pulumi_path | default("pulumi") }}/
├── index.ts              # Entry point — orchestrates all top-level resources
├── Pulumi.yaml           # Project definition (name, runtime, description)
├── Pulumi.<stack>.yaml   # Per-environment config values (encrypted secrets, env config)
└── src/
    ├── services.ts       # Provider API enablements or prerequisites
    ├── managed-secret.ts # ManagedSecret ComponentResource
    ├── runtime-app.ts    # RuntimeApp ComponentResource
    ├── environment.ts    # Environment ComponentResource (groups apps + shared infra)
    ├── ci.ts             # CiTrigger ComponentResource (Cloud Build triggers)
    ├── utils.ts          # Shared helpers (buildComponentAliases, etc.)
    └── configs/          # TypeScript interfaces for stack config shapes
        ├── index.ts      # Re-exports
        ├── environment.ts  # EnvironmentConfig, RuntimeAppConfig, ServiceAccountConfig
        └── secrets.ts    # SecretDefinition discriminated union
```

## ComponentResource Pattern

Every custom resource MUST extend `pulumi.ComponentResource`. This is the core building block.

```typescript
export interface MyComponentArgs {
  location: string;
  project: string;
}

export class MyComponent extends pulumi.ComponentResource {
  public readonly resource: provider.SomeResource;

  constructor(
    name: string,
    args: MyComponentArgs,
    opts?: pulumi.ResourceOptions
  ) {
    super("{{ template.pulumi_project | default("example") }}:components:MyComponent", name, args, opts);

    // All child resources MUST pass parent: this
    this.resource = new provider.SomeResource(
      `${name}-thing`,
      { project: args.project },
      { ...opts, parent: this }
    );

    // Always call registerOutputs at the end
    this.registerOutputs({ resource: this.resource });
  }
}
```

**Rules:**
- URN type format: `<project>:<module>:<ClassName>` — e.g., `{{ template.pulumi_project | default("example") }}:components:RuntimeApp`, `{{ template.pulumi_project | default("example") }}:ManagedSecret`
- Every child resource receives `parent: this` in its `ResourceOptions` — never omit this
- Always call `this.registerOutputs()` at the end of the constructor
- Exported properties are typed `readonly`

## Services-First Dependency Pattern

Provider APIs or prerequisite services must be enabled before any resource that depends on them. All top-level resources pass `dependsOn: services` when the repository uses an explicit service-enablement layer.

```typescript
// services.ts — enable APIs first when the provider requires it
export const primaryApi = new provider.projects.Service("primary-api", {
  service: "service.googleapis.com",
});
export const services = [primaryApi, runtimeApi, ...];

// index.ts — every resource depends on services
new SomeComponent("name", args, { dependsOn: services });
```

## Naming Conventions

| Context | Convention | Example |
|---|---|---|
| Pulumi logical name (1st constructor arg) | `camelCase` | `"{{ template.pulumi_logical_prefix | default("project") }}RuntimeApp"` |
| Provider resource ID (`secretId`, `accountId`, `repositoryId`, etc.) | `kebab-case` | `"{{ template.pulumi_resource_prefix | default("project") }}-api-key"` |
| Converting secret names | `_.camelCase(name)` from lodash | `_.camelCase("MY_SECRET")` |

Use `${name}-suffix` for child resource Pulumi names (e.g., `${name}-sa`, `${name}-logging`).

## Stack Config

- Access config via `new pulumi.Config()` — never use global variables
- `config.requireObject<T>()` for typed non-secret objects
- `config.requireSecretObject<T[]>()` for secret arrays
- Config shape interfaces live in `src/configs/` — define them there, not inline

```typescript
const config = new pulumi.Config();
const envConfig = config.requireObject<EnvironmentConfig>("environment");
const secrets = config.requireSecretObject<SecretDefinition[]>("secrets");
```

## Secret Definitions

Two patterns defined in `SecretDefinition` (discriminated union in `src/configs/secrets.ts`):

```yaml
# Static value — Pulumi-encrypted in Pulumi.<stack>.yaml:
- name: SERVICE_ACCOUNT_KEY
  value:
    secure: v1:abc123...   # Always use 'secure:' prefix, never plaintext

# Auto-generated at deploy time:
- name: INTERNAL_API_KEY
  generate:
    length: 64      # default: 32
    special: false  # default: true
```

**Never commit plaintext secrets.** Use `pulumi config set --secret` to encrypt values.

## Aliases — Safe Resource Renaming

When renaming a Pulumi logical resource (to avoid destroy/recreate), use `buildComponentAliases()`:

```typescript
const sa = new provider.identity.ServiceAccount(
  `${app.name}-sa`,
  { accountId: `${app.name}runtime` },
  {
    parent: this,
    aliases: buildComponentAliases(this, app.serviceAccount.aliases),
  }
);
```

Store previous names in `Pulumi.<stack>.yaml` under the relevant config object's `aliases` field.
Use full URNs (starting with `urn:pulumi:`) when the previous resource had a different parent.

## Outputs

- Export top-level outputs from `index.ts` with `export const`
- Use `pulumi.Output<T>` for values derived from async resource properties
- Use `pulumi.interpolate\`...\`` for string interpolation involving `Output<T>` values
- Use `.apply()` to transform `Output` values — never unwrap with `get()`

## `pulumi.Output` and Async Config

When config values are secret objects (`requireSecretObject`), the result is `Output<T>`. Use `.apply()` to map over them:

```typescript
const secrets = config.requireSecretObject<SecretDefinition[]>("secrets");
const secretResources = secrets.apply((defs) =>
  defs.map((def) => new ManagedSecret(_.camelCase(def.name), { ... }))
);
```

## Verification Commands

```bash
# Always set the (empty) passphrase and log in to the GCS state bucket first —
# see "State Backend & Secrets" above.
export PULUMI_CONFIG_PASSPHRASE=""
pulumi login gs://{{ template.pulumi_project | default("example") }}-pulumi-state

# Preview changes before applying
cd {{ template.pulumi_path | default("pulumi") }} && pulumi preview --stack prod

# Deploy
cd {{ template.pulumi_path | default("pulumi") }} && pulumi up --stack prod

# Encrypt and add a secret to stack config (see "Writing a secret properly")
cd {{ template.pulumi_path | default("pulumi") }} && pulumi config set --secret --stack prod {{ template.pulumi_project | default("example") }}:mySecret "value"
```

Deploy through the Cloud Build CI rather than `pulumi up` by hand — building the
custom Pulumi image and running the pipeline are covered in
{{ skill_path("pulumi-ci-docker") }}.

