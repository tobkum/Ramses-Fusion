# Vendored ramses-py SDK — known defects (upstream report)

Findings from a code audit of the vendored SDK copy in
`Ramses-Fusion/lib/ramses/`. The SDK is deliberately never edited in this
repo (kept replaceable from upstream); defects are either mitigated at
runtime in `lib/ramses_patches.py` / at call sites, or listed here as
upstream-only.

- First audit: 2026-07-15.
- Re-checked: 2026-08-04, against Ramses-Py `d19ce44`. File:line references
  below are against that vendored copy.

## Fixed upstream since the first audit

These were mitigated at runtime here; the patches have since been removed
from `ramses_patches.py`, which now installs nothing (only `DisableMakedirs`
is still live, and that is a Fusion-side concern, not an SDK defect). The
behaviour they guaranteed is still covered by tests, which now assert it of
the vendored SDK itself.

1. **Corrupt sidecar read returned `{}`, and the next write destroyed the
   folder's metadata.** Fixed in Ramses-Py `30582ce`:
   `setFileMetaData` (`metadata_manager.py:199-215`) now refuses to rewrite
   when the read came back empty but the sidecar on disk holds real entries.

2. **Prune-on-read raced threaded copies.** Fixed in `30582ce` (PRs #12/#13):
   `getMetaData` (`metadata_manager.py:178-196`) no longer deletes entries
   whose file does not currently exist, so a version backup still in flight
   from `RamFileManager.copy(separateThread=True)` survives.

3. **Daemon error replies lacked keys the code subscripted.** Fixed in
   `d19ce44` (PR #16): `online` (`daemon_interface.py:100-106`) catches and
   returns False instead of leaking socket exceptions, and
   `__testConnection` (`daemon_interface.py:708-730`) reads the reply with
   `.get` and type checks rather than blind subscripting.

## Still open upstream

4. **`file_manager.py:214/338` — `restoreVersionFile` and `copyToVersion`
   return `None` on malformed names; `publishFile` (`234-240`) returns `None`
   on an empty project. `ram_host.py` callers use the result unchecked**
   (`os.path.dirname(None)` → `TypeError` deep in the save chain).

5. **`ram_settings.py:106-109` — settings JSON parsed at import time with
   no error handling.** A corrupt `ramses_addons_settings.json` raises
   inside the singleton init and makes `import ramses` fail — the entire
   add-on is bricked until the file is manually deleted. (Mitigated here
   by a pre-import quarantine in the entry script.)

6. **`file_info.py:276` — wrong loop variable.** Inside
   `for f in os.listdir(originalPath):` the code calls
   `nm.setFileName( name )` — `name` is a stale outer variable, not `f` —
   so the project-recovery-from-folder-contents fallback never works.

7. **`ram_host.py:1196-1218` — `updateStatus` dereferences a possibly-None
   status for `ItemType.GENERAL`** (`status.state().shortName()` after
   explicitly allowing `status is None` for that item type). Not hit from
   Ramses-Fusion (which overrides `updateStatus`), but any host relying on
   the base implementation crashes for general items.

8. **`ram_settings.py` — cross-process lost updates.** Settings load once
   at init and `save()` serializes the whole stale in-memory dict:
   last-writer-wins between two add-ons/processes. Needs read-merge-write
   or per-key persistence upstream.

9. **`file_info.py:34/64-75` — `__nameRe` cached at class scope.** If first
   built before the daemon/states are available, the regex permanently
   omits state short-names for the process lifetime.

10. **`file_manager.py:413/461` — case-sensitive resource comparison** on
    Windows (the surrounding regex is IGNORECASE); latest-version/publish
    lookups can miss files differing only in case.

11. **`file_manager.py:144-147` — `isProjectFolder` checks
    `os.path.isfile` on a bare basename** (not joined to the folder), so
    it resolves against the CWD; the guard effectively never fires.

12. **`daemon_interface.py` — `_cache` (class scope, line 63; mutated at
    777-786) is written outside `_socket_lock`, and `instance()` (83-91)
    builds the singleton without a guard**; racy under threaded hosts.
