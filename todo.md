# Ramses-Fusion Workflow Improvements TODO

This list contains proposed improvements to elevate the Ramses-Fusion plugin for professional VFX workflows.

## Core Plugin Improvements (Robustness & Integration)
- [ ] **Internal Metadata Persistence**
    - Store Ramses UUIDs (Item, Step, Project) directly inside the Fusion composition data (`comp.SetData()`).
    - Makes the file "self-aware" even if moved or renamed outside of Ramses.
- [ ] **Version Comment Display**
    - Pull the comment for the currently active file version from the Ramses sidecar metadata and display it in the UI header.
    - Keeps artist notes ("Fixed glow", "Retimed") immediately visible.
- [ ] **Production Notes Integration**
    - Pull official "Instructions" or "Task Briefing" from the Ramses database and display them in the UI.
- [ ] **Project Audit Tool**
    - Scan the scene for consistency: warn if an imported asset belongs to a different project or if FPS doesn't match project standards.
- [ ] **Dependency Tracking (Ramses "Uses")**
    - Automatically update the Ramses database when assets/renders are imported, linking dependencies between tasks.

## High Priority Workflow Features
- [ ] **Automated Preview Generation**
    - Implement the "Create Preview" action:
        - Dynamically attach a temporary lightweight `Saver` (H.264/MP4) to the **currently selected node**.
        - Render the shot frame range.
        - Automatically delete the temporary `Saver` node after completion.
        - Register the preview file in the Ramses database for instant review.
- [ ] **Full Publish Workflow (Final Delivery)**
    - Upgrade the "Publish" checkbox logic in the Status Update dialog:
        - Read centralized **Global Render Specifications** (EXR/ProRes) from Ramses settings.
        - Automate a final-quality render to the official Ramses `Published` folder.
        - Save a backup copy of the `.comp` file alongside the renders.
        - Register all rendered sequences in the Ramses database and update downstream dependencies.
- [ ] **Smart Saver Setup (Automated Rendering)**
    - Add a "Setup Saver" button to create a `Saver` node pre-configured with Ramses-compliant paths.
- [ ] **Loader Version Control (Version Up/Down)**
    - Add buttons to "Version Up" or "Version Down" selected `Loader` nodes.
    - Scan Ramses directories to find existing versions and update paths instantly.

## Advanced Integration & Automation
- [ ] **Global Render Specifications (Project-wide Formats)**
    - Implement a system to read render specs (EXR, ProRes, etc.) from Ramses Project/Step settings.
- [ ] **Smart Loader Alignment**
    - Automatically adjust the `Global In` of all `Loader` nodes to match the Ramses start frame (e.g., 1001) during "Setup Scene".
- [ ] **Self-Aware Composition (Automatic Context)**
    - Trigger a context refresh every time a Comp is opened or saved by reading stored metadata.
- [ ] **Loader Version Scanner (Audit Tool)**
    - "Audit Scene" button to scan all Loaders and highlight outdated versions (e.g., turning the node tile red in the Flow).
- [ ] **Right-Click Context Menus**
    - Add a "Ramses" submenu to Loader/Saver nodes for quick versioning or showing items in the Ramses Client.
- [ ] **Automated Burn-in / Slates**
    - Tool to generate a `Text+` node or slate pre-populated with live Ramses metadata.

## Quality of Life
- [ ] **User Role Awareness**
    - Grey out or warn on "Publish" if the current user role does not have permission to publish final versions.
- [ ] **Batch Status Update**
    - Option to update status/comments for all imported assets (Loaders) directly from the Fusion UI.
- [x] **Contextual Refresh**
    - Automatically refresh the UI header when a new file is opened, saved, or switched via the plugin.
- [ ] **Live Context Refresh**
    - Automatically refresh the UI header when switching between multiple open compositions in Fusion.
