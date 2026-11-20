# Stage complete clients for the core runtime

After host provisioning and core-stack installation, run this as the ordinary operator who owns both receipts/state:

```bash
python3 scripts/stage-clients.py \
  --host-receipt /private/hostctl/receipts/QUALIFIED_RECEIPT.json \
  --state /private/core-stack/state \
  --names codex,claude,python,native-profiles
```

Use the selected verified Python instead of `python3` when its host entry point differs. The helper does not require Docker, call models, run package installation or change host-global paths.

Every requested name must exist in a verified hostctl receipt for the same operator. Its complete versioned source tree must still match the recorded tree identity. A reused standalone executable is an explicit blocker because it does not establish the runtime's library/dependency closure; normalize a complete qualified tree first. The core state must already have its valid `agentic-install.json` ownership marker.

The helper copies the complete trees, preserving their layout and relative links, into `runtime/clients/<name>/<version>-<tree-hash-prefix>`. Promotion is atomic and refuses to replace an existing destination. A matching existing version is verified and reused; changed files or foreign/symlink destinations are preserved and reported as blockers. Old version directories remain available for rollback. No `current` alias is changed.

`reports/client-runtime.json` records the source receipt/hash, source tree identities, host destinations, immutable `/opt/agentic/clients/...` container paths and each declared command's container path. Use those exact paths in the site-specific native-profile plan. `profilePlanHints` identifies staged Python commands and the native-profile asset root when selected. Prior reports are retained as versioned report backups.

This is a **copy-and-identity qualification** only. It does not execute or install native profiles and does not establish container compatibility, model authentication, tool calls or hooks. Invoke the real native-profile installer with the selected Python as the ordinary operator in its intended environment, then verify the staged commands and profiles inside the actual Paperclip/worker runtime. Host qualification alone does not prove that the container supplies every required system library.
