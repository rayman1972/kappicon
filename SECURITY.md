# Security policy

## Supported versions

| Version | Supported |
|---------|-----------|
| Latest release on GitHub / AUR `kappicon` | Yes |
| `main` / AUR `kappicon-git` | Best effort |
| Older tags | No guarantees |

## What this project does

kAppIcon edits **user-level** freedesktop data (for example
`~/.local/share/applications` and user icon themes). It is designed **not** to
require root and **not** to modify system packages under `/usr` as a normal
operation.

## Reporting a vulnerability

Please **do not** open a public issue for security-sensitive reports.

Prefer one of:

1. **GitHub Security Advisories** for this repository  
   (Security → Report a vulnerability), if enabled for the repo  
2. A **private** contact to the maintainer via GitHub (e.g. security advisory
   or maintainer DM if you already communicate that way)

Include:

* Description of the issue and impact
* Steps to reproduce
* Affected version / commit
* Whether a fix is already known

We will acknowledge reports as soon as practical and work on a fix before any
public disclosure when that is reasonable.

## Non-security bugs

Icon not updating, wrong app listed, packaging issues, etc. → public
[GitHub Issues](https://github.com/rayman1972/kappicon/issues) with the bug
template.
