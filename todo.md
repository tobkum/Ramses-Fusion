# Ramses-Fusion Workflow Improvements TODO

This list tracks planned improvements to elevate the Ramses-Fusion plugin for professional VFX workflows.

## Completed Code Improvements (2026-01-15/17)
- [x] **Robustness**: Fixed all bare `except` blocks with specific logging.
- [x] **Safety**: Added null checks for critical status objects.
- [x] **Bug Fix**: Resolved circular reference in About window.
- [x] **Optimization**: Batched `SetPrefs()` calls (5 -> 1).
- [x] **Code Quality**: Implemented `@requires_connection` decorator (-22 lines of boilerplate).
- [x] **Documentation**: Added type hints (19 methods) and docstrings (26 methods).
- [x] **New Feature**: Internal Metadata Persistence (UUIDs embedded in `.comp`).
- [x] **Safety**: Strict Project Context Enforcement (Blocks cross-project work).
- [x] **Security**: Role-Based UI State Management (Conditional access for "Step Configuration" button; supports solo vs. multi-user logic).
- [x] **UX/UI**: Modernized Context Header ("Hero ID" hierarchy, Ramses-synced Step/State colors).
- [x] **UX/UI**: Live Priority Indicators (Heat-mapped '!', '!!', '!!!' markers).
- [x] **UX/UI**: Professional Dialog Engine (Non-editable labels, semantic button labels, and two-tier validation hierarchy).
- [x] **Code Quality**: Standardized path resolution in `fusion_host.py` using `_get_preset_settings` helper; eliminated redundant logic across `resolvePreviewPath` and `resolveFinalPath`.
- [x] **Bug Fix**: Resolved "Double Extension" bug in sequence path generation.
- [x] **Workflow**: Implemented dynamic zero-padding for image sequences based on shot frame range.
- [x] **Configuration**: Global Render Specifications (Step-level YAML overrides for codec, format, and sequence settings).
- [x] **QA**: Post-Render Verification (Wildcard sequence matching and 0-byte integrity checks).
- [x] **Code Quality**: Removed significant code duplication in `fusion_config.py` (Parser and Extract methods) and verified with 39 unit tests.
- [x] **Robustness**: Hardened Lua parser to support scientific notation and comments.
- [x] **Safety**: Transactional Publish Workflow (Strictly requires `_FINAL` anchor; aborts all operations if render fails).
- [x] **UX/UI**: Modernized Step Configuration Wizard with responsive layout (1000x800) and automated sequence detection.

---

## Robustness & Safety (Production Critical)
- [ ] **Atomic File Operations**
    - Implement transaction-like saves: write to temp file first, then rename to ensure no corruption on crash.
- [ ] **File Locking / Conflict Detection**
    - [ ] **Mechanism**: "Soft Locking" via hidden sidecar files (`.~filename.comp.lock`) containing User/Machine info.
    - [ ] **Hooks**:
        - `on_open`: Check for lock. If exists -> Prompt (Read-Only / Console / Steal).
        - `on_close`: Release lock.
    - [ ] **UX**: Visual indicator (🔓/🔒) in header. Heartbeat to prevent stale locks.
- [ ] **Write Permission Validation**
    - Pre-check write permissions on target directories before attempting render/save/publish actions.

## Pipeline Intelligence
- [ ] **Dependency Tracking (Ramses "Uses")**
    - Automatically register imported assets in Ramses to track "This shot uses Asset X v002".
- [ ] **Outdated Asset Detection**
    - "Audit Scene" tool: Scan all Loaders and warn if newer published versions exist in the DB.
- [ ] **Frame Range Validation on Import**
    - Verify imported EXR sequences match the Loader's length and the Ramses shot duration.
- [ ] **Project Consistency Audit**
    - Warn if an imported asset belongs to a different project or has mismatched FPS.

## Workflow Enhancements
- [ ] **Render Farm Integration**
    - Submit jobs to Deadline/OpenCue/etc. with proper metadata (frames, output path, user) instead of local render.
- [ ] **Batch Operations**
    - "Update All Loaders": One-click update all assets to latest version.
    - "Batch Status": Update status for multiple loaded assets at once.
- [ ] **Automated Slates / Burn-ins**
    - Generator tool for `Text+` node populated with live metadata (Shot, Version, Artist, Date).
- [ ] **Loader Version Control**
    - Context menu or buttons to "Version Up/Down" selected Loader nodes.
- [ ] **Notification Webhooks (ChatOps)**
    - Send "High Signal" events (Publish, Status Change, Render Fail) to Google Chat/Slack.
    - Use async fire-and-forget to prevent UI lag.
    - **Goal**: replace "email storms" with targeted channel notifications.

## Production Compliance
- [ ] **Extended Role-Based UI State Management**
    - Extend dynamic enablement/disablement to other UI elements (e.g., Publish button, Admin tools) based on the authenticated user's permissions.
- [ ] **Approval Workflow**
    - Require Supervisor 'Approved' status in Ramses before allowing a 'Final' publish.
- [ ] **Audit Trail**
    - Log structured events (Saved, Published, Imported) to a central production log file.

## Quality Assurance
- [ ] **Pre-Render Validation**
    - Sanity check before render: Unconnected nodes, missing media, tools left in PassThrough.

## Performance
- [ ] **Background Status Fetching**
    - Fetch shot statuses in a background thread to prevent UI freezing during navigation.
- [ ] **Lazy Project Loading**
    - Load heavy project data only when needed, not at plugin startup.

---

## Future UX & Workflow Polish
- [ ] **Navigation & Accessibility**
    - [ ] **Searchable Shot Wizard**: Add a filter bar to the Switch Shot dialog for large projects.
    - [ ] **Recent/Pinned Items**: Quick-access list for current active tasks.
    - [ ] **The "Summoner"**: Global hotkey to pop up the UI at the mouse cursor position.
- [ ] **Visual Feedback & Awareness**
    - [ ] **Visual Thumbnails**: Display Ramses preview frames in Version/Shot selection.
    - [x] **Contextual Header Badges**: Dynamic colored status/priority tags in the header.
    - [ ] **Outdated Asset Scanner**: Badge notification if Loader nodes have newer versions in Ramses.
- [ ] **Interface & Layout**
    - [x] **Collapsible Sections**: Allow folding away groups (e.g., Assets, Settings) to save space.
    - [ ] **Horizontal Action Bar**: Ultra-slim secondary UI mode for single-monitor setups.
- [ ] **Pipeline Intelligence**
    - [ ] **Auto-Healing Validation**: One-click "Fix All" for technical mismatches.
    - [ ] **Structured Log Viewer**: Dedicated panel for Ramses-specific events and errors.