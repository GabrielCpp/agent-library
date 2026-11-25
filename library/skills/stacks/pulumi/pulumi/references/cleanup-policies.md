# Artifact Registry cleanup policies

The standard set for a Docker repository that serves Pulumi-managed Cloud Run apps. Declare all three.

```typescript
const servicePackages = environment.cloudRunApps.map(app => app.name);

cleanupPolicies: [
  {
    id: "keep-tagged",
    action: "KEEP",
    condition: {
      tagState: "TAGGED",        // tagged = deployed/in-use — never delete
      packageNamePrefixes: servicePackages,
    },
  },
  {
    id: "keep-recent-5",
    action: "KEEP",
    mostRecentVersions: {
      keepCount: 5,              // safety net: keep 5 most recent per package
      packageNamePrefixes: servicePackages,
    },
  },
  {
    id: "delete-untagged-old",
    action: "DELETE",
    condition: {
      tagState: "UNTAGGED",
      olderThan: "86400s",       // build cache / overwritten :latest digests
      packageNamePrefixes: servicePackages,
    },
  },
],
cleanupPolicyDryRun: false,
```
