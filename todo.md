# Ramses-Fusion Workflow Improvements TODO

This list tracks planned improvements to elevate the Ramses-Fusion plugin for professional VFX workflows.

## Completed Code Improvements (2026-01-15)
- [x] **Robustness**: Fixed all bare `except` blocks with specific logging.
- [x] **Safety**: Added null checks for critical status objects.
- [x] **Bug Fix**: Resolved circular reference in About window.
- [x] **Optimization**: Batched `SetPrefs()` calls (5 -> 1).
- [x] **Code Quality**: Implemented `@requires_connection` decorator (-22 lines of boilerplate).
- [x] **Documentation**: Added type hints (19 methods) and docstrings (26 methods).

---

## Robustness & Safety (Production Critical)
- [ ] **Atomic File Operations**
    - Implement transaction-like saves: write to temp file first, then rename to ensure no corruption on crash.
- [ ] **File Locking / Conflict Detection**
    - Check if another user has the shot open before saving using Ramses lock API.
- [ ] **Write Permission Validation**
    - Pre-check write permissions on target directories before attempting render/save/publish actions.
- [ ] **Internal Metadata Persistence**
    - Store Ramses UUIDs (Item, Step, Project) directly inside Fusion `comp.SetData()` for resilience.

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
    - Submit jobs to Deadline/Tractor with proper metadata (frames, output path, user) instead of local render.
- [ ] **Batch Operations**
    - "Update All Loaders": One-click update all assets to latest version.
    - "Batch Status": Update status for multiple loaded assets at once.
- [ ] **Automated Slates / Burn-ins**
    - Generator tool for `Text+` node populated with live metadata (Shot, Version, Artist, Date).
- [ ] **Loader Version Control**
    - Context menu or buttons to "Version Up/Down" selected Loader nodes.

## Production Compliance
- [ ] **User Role Permissions**
    - Disable "Publish" button if user role (e.g., 'Artist') lacks publish rights in Ramses.
- [ ] **Approval Workflow**
    - Require Supervisor 'Approved' status in Ramses before allowing a 'Final' publish.
- [ ] **Audit Trail**
    - Log structured events (Saved, Published, Imported) to a central production log file.

## Quality Assurance
- [ ] **Pre-Render Validation**
    - Sanity check before render: Unconnected nodes, missing media, tools left in PassThrough.
- [ ] **Post-Render Verification**
    - Verify file existence, sequence length, and file size to catch corrupted frames.

## Performance
- [ ] **Background Status Fetching**
    - Fetch shot statuses in a background thread to prevent UI freezing during navigation.
- [ ] **Lazy Project Loading**
    - Load heavy project data only when needed, not at plugin startup.

---

## Configuration & Customization
- [ ] **Global Render Specifications**
    - Read render specs (codec, resolution, naming) from Ramses Project/Step YAML settings instead of hardcoding.
    - _Example YAML:_
      ```yaml
      render_presets:
        Preview: { format: "QuickTimeMovies", codec: "Apple ProRes 422_apcn" }
        Final: { format: "QuickTimeMovies", codec: "Apple ProRes 4444_ap4h" }
      ```