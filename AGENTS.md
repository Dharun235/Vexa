# Working practices

- Work on a feature branch, not directly on `main`.
- Keep implementations small, avoid redundant code, and favour CPU inference with low resource use.
- Run the focused checks needed to verify a change before considering it complete.
- After verification, remove task-created temporary environments, test input/output copies, obsolete local build artifacts, and caches no longer needed.
- Keep active environments and their Python runtimes, current release artifacts, lockfiles, and required development inputs.
- Preserve user-provided data and custom models. Do not treat published releases or Git history as disposable caches.
- Summarise the result and cleanup. Follow `CONTRIBUTING.md` for package and release work.
