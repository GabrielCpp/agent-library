---
name: private-names
description: "The rule for a public repo that sits beside private client work: no private project name enters a tracked file, a path or a commit message. The names live outside the repo, in `$STABLEMATE_PRIVATE_NAMES` or `$GIT_DIR/private-names`, and an agent commit check refuses a commit whose staged files or message carry one."
commit_checks:
  - run: scripts/check_private_names.py
    budget: 2
---

## Private project names stay out

This repo is public. A private project name never enters a tracked file, a path or
a commit message. Write a neutral placeholder instead: acme, globex, api-service,
web-app, mobile-app, example.com. The list lives in `$STABLEMATE_PRIVATE_NAMES` or
`$GIT_DIR/private-names`. Never print it or copy it into a tracked file.

A commit check refuses each staged line that carries a name. A name already in
history needs `git filter-repo --replace-text`, not a removal commit.
