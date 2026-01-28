# Ramses-Fusion Workflow Improvements TODO

## Completed Code Improvements
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
- [x] **New Feature**: Dual Export Pipeline Support (Toggle between "Project Export" and "Step Export" destinations via Step Config Wizard).

---

## Robustness & Safety (Production Critical)
- [ ] **Atomic File Operations**
    - Implement transaction-like saves: write to temp file first, then rename to ensure no corruption on crash.
- [ ] **File Locking / Conflict Detection**
    - [ ] **Mechanism**: "Soft Locking" via hidden sidecar files (`.~filename.comp.lock`) containing User/Machine/PID/Timestamp.
    - [ ] **Global Watchdog (Heartbeat)**:
        - Implement a singleton background thread (`Watchdog`) that runs every 30-60s.
        - **Logic**: 
            1. Query `fusion.GetCompList()` to find *all* open compositions (active and background tabs).
            2. **Maintain**: For every open file, update its lock timestamp ("heartbeat").
            3. **Release**: Identify files that were previously locked but are no longer in the open list (User closed the tab) and delete their lock files.
            4. **Acquire**: If a user opens a new file (via File>Open), automatically attempt to acquire a lock.
    - [ ] **Stale Lock Handling**:
        - If a lock's timestamp is > 2 minutes old (meaning the Watchdog crashed), treat it as "Stale" and allow the new user to overwrite/steal it.
    - [ ] **UX**: Visual indicator (🔓/🔒) in header. Prompt user on Open if a valid lock exists (Read-Only / Force Unlock).
- [ ] **Write Permission Validation**
    - Pre-check write permissions on target directories before attempting render/save/publish actions.
- [ ] **Critical: Lock Pipeline Nodes**
    - **Goal**: Prevent accidental user modification of pipeline-critical nodes (`_PREVIEW`, `_FINAL`).
    - **Implementation**: After "Sync Project Settings" or "Setup Scene", automatically set the `Locked` attribute on these nodes.
    - **UX**: Nodes remain inspectable but cannot be deleted or have their settings (format, path, resolution) changed without explicit unlocking.

## Pipeline Intelligence
- [ ] **Dependency Tracking (Ramses "Uses")**
    - Automatically register imported assets in Ramses to track "This shot uses Asset X v002".
    - **Integration**: Trigger this registration when using the proposed "Smart Import" dialog (see below).
- [ ] **Outdated Asset Detection**
    - "Audit Scene" tool: Scan all Loaders and warn if newer published versions exist in the DB.
- [ ] **Frame Range Validation on Import**
    - Verify imported EXR sequences match the Loader's length and the Ramses shot duration.
- [ ] **Project Consistency Audit**
    - Warn if an imported asset belongs to a different project or has mismatched FPS.

## Workflow Enhancements

- [ ] **Production Feedback Stream**
    - **Goal**: Allow artists to view supervisor feedback and version history directly within Fusion, eliminating the need to alt-tab to external tools.
    - **UI**: A dedicated "History" tab or collapsable panel showing a timeline of comments for the current Shot/Task.
    - **Features**: 
        - Read-only list of comments (e.g., `v002 (Supervisor): "Blur the background more."`).
        - Visual distinction between "Artist Notes" and "Supervisor/Client Feedback".
- [ ] **Quick Access: "Open Output Folder"**
    - **Goal**: One-click access to the OS directory for previews and final renders, reducing navigation friction.
    - **Implementation**: Small folder icon buttons next to "Create Preview" and "Update / Publish".
    - **Logic**: Resolves the path using `FusionHost.resolveFinalPath` / `previewPath` and opens the directory.
- [ ] **Smart Import Dialog ("Pipeline Loader")**
    - **Goal**: Replace the native file browser with a context-aware dialog for importing assets and step renders.
    - **Features**:
        - **Contexts**: Toggle between "Current Shot" (upstream steps) and "Global Assets".
        - **Selectors**: Step (e.g., Lighting, FX) -> Version (Latest/Approved).
        - **Metadata**: Automatically tags imported Loaders with Source UUIDs for dependency tracking.
- [ ] **Intermediate/Cache File Strategy**
    - **Goal**: Define a standard location for pre-renders (masks, particles) that persist across script versions (avoiding re-renders on `v001`->`v002`).
    - **Proposal**: Use a `_cache` folder at the **Step Root** (sibling to `_versions` and `_published`).
    - **Tasks**: 
        - Verify API safety (ensure `_cache` doesn't conflict with Ramses logic).
        - define naming convention for cache elements (independent versioning?).
- [ ] **Customizable Preview Specs**
    - Allow users to toggle high-level render settings for PREVIEW renders (e.g., HiQ on/off, Motion Blur toggle, and Proxy Resolution overrides).
- [ ] **Render Farm Integration**
    - Submit jobs to Deadline/OpenCue/etc. with proper metadata (frames, output path, user) instead of local render.
- [ ] **Batch Operations**
    - "Update All Loaders": One-click update all assets to latest version.
    - "Batch Status": Update status for multiple loaded assets at once.
- [ ] **Data-Driven Auto-Slate ("Ramses Slate")**
    - **Goal**: Eliminate manual data entry and typos in slates.
    - **Mechanism**: A custom Fusion Tool (Fuse/Macro) with **no manual text inputs**.
    - **Logic**: Pulls all data dynamically from the Ramses Daemon at render-time:
        - Show Name, Shot Code, Artist Name (Current User).
        - Status (e.g., "Ready for Review"), Date, Frame Count.
        - Technical Metadata (Lens info, Resolution, Colorspace).
    - **Value**: Guaranteed accuracy; the slate is a direct reflection of the database state.
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
    - [ ] **Auto-Hide UI (Ghost Mode)**: Implement a mode where the plugin automatically collapses to its header (or title bar) when not in use, expanding only when the mouse hovers over it or it receives focus.
    - [ ] **Horizontal Action Bar**: Ultra-slim secondary UI mode for single-monitor setups.
- [ ] **Pipeline Intelligence**
    - [ ] **Auto-Healing Validation**: One-click "Fix All" for technical mismatches.
    - [ ] **Structured Log Viewer**: Dedicated panel for Ramses-specific events and errors.