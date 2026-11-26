# Security policy

## Reporting a vulnerability

Please report security issues privately, through GitHub's
[private vulnerability reporting](https://github.com/GabrielCpp/agent-library/security/advisories/new)
on this repository. Do not open a public issue.

Include the affected file, what an attacker gains and the smallest reproduction you have.
You will get an acknowledgement within a week. This is a small project maintained in spare
time, so treat that as a best effort rather than an SLA.

## Supported versions

Fixes land on `main`. There are no releases or back-ports. The latest commit is the
supported one.

## What this library does, in security terms

**Its content becomes agent instructions.** farrier renders these skills, prompts and root
files into the files an agent CLI reads at startup. Review a library you did not write the
way you would review code you are about to run.

**Its hooks run on every tool call.** The scripts under `library/hooks/` run as Claude Code
hooks with your user's permissions. They read the tool call and the session transcript, and
they can block a call. Read a hook before you install it.

**Its settings change agent permissions.** `library/settings/*.json` merges into your agent
CLI settings on a home install. Check the permission and hook entries before you merge them.

**It holds no secrets.** Credentials stay outside the repository, in
[saddlebag](https://github.com/GabrielCpp/stablemate/tree/main/saddlebag) or your own
secret store.
