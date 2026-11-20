# Security and deployment boundaries

## Reporting a vulnerability

For a vulnerability that could expose credentials, escape an installation boundary, corrupt preserved configuration or install untrusted artifacts, use [private vulnerability reporting](https://github.com/Idoheled/agentic-foundry/security/advisories/new) with a minimal reproduction and the affected release tag. Do not publish secrets or exploit details in a public issue. If private reporting is unavailable, open a sanitized issue requesting a private contact channel without describing exploit details or including sensitive evidence.

Ordinary installation failures and feature requests belong in the issue templates.

## Supported scope

Security fixes target the current development branch and the latest published release. A release's documented platform and payload profile define its supported installation scope. Older release artifacts remain immutable records; fixes are published under a new version.

Agentic Foundry's integration code does not replace the upstream security policies or licenses of bundled projects. Report an upstream defect to its maintainer and reference the affected artifact identity here so a replacement can be qualified.

## Deployment boundaries

- Inspect the actual machine and private supply before selecting artifacts.
- Verify release and payload hashes before executing supplied runtimes.
- Preserve native package ownership and complete runtime dependency layouts.
- Keep credential values, internal routes, private site files and state outside Git.
- Keep each client's supported sandbox and approval semantics intact. An auto-mode installation authorization is scoped to the requested deployment.
- Preserve the original profile baseline throughout an existing-machine upgrade.
- Qualify real model, tool, worker and browser behavior before enabling the corresponding capability.

Source CI validates integration behavior using isolated fixtures. It does not certify private models, native system changes or arbitrary target projects.

## Release automation

Pull-request checks use a read-only repository token and skip LFS payload downloads. The release publication workflow is manual, verifies an existing annotated tag and the real LFS object bytes (locally or by bounded remote streaming), and attaches assets to a draft before publication. It refuses to overwrite an existing release. Review changes to workflows, payload manifests and installation policy as executable supply-chain changes.
