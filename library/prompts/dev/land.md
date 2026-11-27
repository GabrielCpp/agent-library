---
description: Land the work on the main branch, then remove every worktree and branch this session created
---

Land the work on the main branch and dispose of all your worktrees and branches. Land each branch with a `git merge --ff-only` to avoid creating merge commits. rebase the branch on the main branch if it is not up to date.
