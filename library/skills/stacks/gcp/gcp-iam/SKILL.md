---
name: gcp-iam
description: "GCP IAM in Pulumi: additive *IamMember over *IamBinding or *IamPolicy. Load when granting a role to a service account or user in Pulumi, reviewing IAM resources, migrating Binding to Members, or diagnosing a role that vanished after deploy."
applyTo: '{{ template.pulumi_path | default("pulumi") }}/**/*.ts'
tags: [infra, standards]
---

# GCP IAM Conventions

How to grant IAM on GCP resources (secrets, buckets, projects, topics, …) without
principals silently knocking each other out of a policy. Tool-agnostic, but the
resource names below are the Pulumi/Terraform `google` provider forms.

## Additive `*IamMember`, not authoritative `*IamBinding`

For a shared resource, **default to the additive `*IamMember` resource, not the
authoritative `*IamBinding`** (and almost never the whole-resource `*IamPolicy`).

- `<svc>.<Res>IamMember` — **additive**: manages one `(resource, role, member)`
  and leaves other members of that role intact.
- `<svc>.<Res>IamBinding` — **authoritative for that `(resource, role)` pair**:
  declares the *complete* member list and overwrites anything else holding the role.
- `<svc>.<Res>IamPolicy` — **authoritative for the entire resource** (all roles).

The trap: when **two principals share the same resource + role** — e.g. an API and
a report service account both need `roles/secretmanager.secretAccessor` on one
secret, or both need `roles/storage.objectAdmin` on one bucket — two authoritative
`*IamBinding` resources each declare a one-member list and **clobber each other**.
The policy ends up with a single member, or (mid-apply, when one is deleted or
replaced) *empty*. The dependent workload then dies with `PermissionDenied`. It is
silent: each binding looks correct in isolation, and the breakage may only surface
on the next deploy or cold start.

```typescript
// WRONG — two authoritative bindings on the same secret+role fight; the policy
// ends up with one member (or empty during a replace), so the other SA 403s.
new gcp.secretmanager.SecretIamBinding("api-db",    { secretId, role, members: [apiSa] });
new gcp.secretmanager.SecretIamBinding("report-db", { secretId, role, members: [reportSa] });

// RIGHT — additive members coexist.
new gcp.secretmanager.SecretIamMember("api-db",    { secretId, role, member: apiSa });
new gcp.secretmanager.SecretIamMember("report-db", { secretId, role, member: reportSa });
```

Reserve `*IamBinding` for when you deliberately own the *entire* member set of a
role and want out-of-band additions reverted. Reserve `*IamPolicy` for almost
never. **When in doubt, use `*IamMember`.**

## Migrating Binding → Member

Switching an existing `*IamBinding` to `*IamMember` is a **replace**: the
authoritative delete can transiently empty the policy mid-apply. So after the
change, re-grant the members (or re-run the apply) and confirm:

```bash
gcloud secrets get-iam-policy <secret> --project <project>
gcloud storage buckets get-iam-policy gs://<bucket>
# add a single member out-of-band if you need to unblock immediately:
gcloud secrets add-iam-policy-binding <secret> \
  --member="serviceAccount:<sa>" --role="roles/secretmanager.secretAccessor"
```

