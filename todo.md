# Ramses-Fusion Workflow Improvements TODO

This list contains proposed improvements to elevate the Ramses-Fusion plugin for professional VFX workflows.

## Core Plugin Improvements (Robustness & Integration)
- [ ] **Internal Metadata Persistence**
    - Store Ramses UUIDs (Item, Step, Project) directly inside the Fusion composition data (`comp.SetData()`).
    - Makes the file "self-aware" even if moved or renamed outside of Ramses.
- [ ] **Live Context Refresh**
    - Automatically refresh the UI header and internal context when switching between multiple open compositions in Fusion.
- [ ] **Dependency Tracking (Ramses "Uses")**
    - Automatically update the Ramses database when assets/renders are imported, linking dependencies between tasks.
- [ ] **Publish "Pre-flight" Check**
    - Validation before publishing: check for local file paths in Loaders, frame range mismatches, and missing frames.

## High Priority Workflow Features
- [ ] **Smart Saver Setup (Automated Rendering)**
    - Add a "Setup Saver" button to create a `Saver` node pre-configured with Ramses-compliant paths.
    - Automatically set file formats (OpenEXR/DNxHR), naming conventions (Project_Item_Step_v001.exr), and color space.
- [ ] **Loader Version Control (Version Up/Down)**
    - Add buttons to "Version Up" or "Version Down" selected `Loader` nodes.
    - Scan Ramses directories to find existing versions and update paths instantly.
- [ ] **Right-Click Context Menus**
    - Add a "Ramses" submenu to Loader/Saver nodes:
        - Version Up / Version Down.
        - Open Folder in Explorer.
        - Show Item in Ramses Client.

## Advanced Integration & Automation
- [ ] **Self-Aware Composition (Automatic Context)**
    - Trigger a context refresh every time a Comp is opened or saved by reading stored metadata.
- [ ] **Loader Version Scanner (Audit Tool)**
    - "Audit Scene" button to scan all Loaders and highlight outdated versions (e.g., turning the node tile red in the Flow).
- [ ] **Automated Burn-in / Slates**
    - Tool to generate a `Text+` node or slate pre-populated with live Ramses metadata (Project, Shot, Version, Date, Artist) using expressions.

## Quality of Life
- [ ] **Batch Status Update**
    - Option to update status/comments for all imported assets (Loaders) directly from the Fusion UI.
- [ ] **Contextual Refresh**
    - Automatically refresh the UI header when a new file is opened or saved.
