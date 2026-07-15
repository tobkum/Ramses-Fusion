# Vendored ramses-py SDK — known defects (upstream report)

Findings from a full code audit (2026-07-15) of the vendored SDK copy in
`Ramses-Fusion/lib/ramses/`. The SDK is deliberately never edited in this
repo (kept replaceable from upstream); defects are either mitigated at
runtime in `lib/ramses_patches.py` / at call sites, or listed here as
upstream-only. File:line references are against this repo's vendored copy.

## Mitigated at runtime in this repo (see `ramses_patches.py`)

1. **`metadata_manager.py:185` — corrupt sidecar read returns `{}`, next
   write destroys the folder's metadata.** `getMetaData` returns an empty
   dict after 3 failed parse attempts; `setFileMetaData` (203-209) merges
   one entry into that empty dict and rewrites `_ramses_data.json`,
   wiping every other file's comments/history/version info. Trigger: any
   process (e.g. the Ramses client) writing the sidecar non-atomically at
   the moment of the read. Suggested upstream fix: distinguish
   "unreadable" from "empty" and refuse the rewrite, plus atomic writes
   everywhere (this copy's `setMetaData` is already atomic).

2. **`metadata_manager.py:191-197` — prune-on-read races threaded
   copies.** `getMetaData` deletes entries whose file doesn't exist; a
   version backup copied via `RamFileManager.copy(separateThread=True)`
   is invisible to `os.path.isfile` while in flight, so the immediately
   following `appendHistoryDate`/`setComment` prunes and persists.
   Suggested upstream fix: don't prune on read (or prune only entries
   older than some threshold).

3. **`file_manager.py:339/231/206` — `copyToVersion`,
   `restoreVersionFile`, `publishFile` return `None` on malformed names;
   `ram_host.py` callers use the result unchecked** (`os.path.dirname(None)`
   → `TypeError` deep in the save chain).

4. **`daemon_interface.py:657-701` — error replies lack keys the code
   subscripts.** `__post`'s error dict has no `content`;
   `__testConnection` (line 701) does `data['content']` → `KeyError`, so
   `online()` raises instead of returning False. `sendall`/`recv` are
   also outside the try (635-642 only guards `connect`), so a daemon
   dying mid-reply raises `ConnectionResetError` out of documented
   "returns None if unavailable" APIs.

5. **`ram_settings.py:107-109` — settings JSON parsed at import time with
   no error handling.** A corrupt `ramses_addons_settings.json` raises
   inside the singleton init and makes `import ramses` fail — the entire
   add-on is bricked until the file is manually deleted. (Mitigated here
   by a pre-import quarantine in the entry script.)

## Upstream-only (not mitigated here; low frequency or design-level)

6. **`file_info.py:276` — wrong loop variable.** Inside
   `for f in os.listdir(originalPath):` the code calls
   `nm.setFileName( name )` — `name` is a stale outer variable, not `f` —
   so the project-recovery-from-folder-contents fallback never works.

7. **`ram_host.py:1213-1225` — `updateStatus` dereferences a possibly-None
   status for `ItemType.GENERAL`** (`status.state()` after explicitly
   allowing `status is None`). Not hit from Ramses-Fusion (which overrides
   `updateStatus`), but any host relying on the base implementation
   crashes for general items.

8. **`ram_settings.py` — cross-process lost updates.** Settings load once
   at init and `save()` serializes the whole stale in-memory dict:
   last-writer-wins between two add-ons/processes. Needs read-merge-write
   or per-key persistence upstream.

9. **`file_info.py:64-75` — `__nameRe` cached at class scope.** If first
   built before the daemon/states are available, the regex permanently
   omits state short-names for the process lifetime.

10. **`file_manager.py:413/461` — case-sensitive resource comparison** on
    Windows (the surrounding regex is IGNORECASE); latest-version/publish
    lookups can miss files differing only in case.

11. **`file_manager.py:145-147` — `isProjectFolder` checks
    `os.path.isfile` on a bare basename** (not joined to the folder), so
    it resolves against the CWD; the guard effectively never fires.

12. **`daemon_interface.py` — `_cache` mutated outside `_socket_lock`,
    and `instance()` builds the singleton without a guard**; racy under
    threaded hosts.
