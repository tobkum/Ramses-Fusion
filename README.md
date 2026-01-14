# Ramses-Fusion

**Ramses-Fusion** is a bridge between the [Ramses](https://ramses.rxlab.guide/) pipeline ecosystem and Blackmagic Fusion. Developed by [**Overmind Studios**](https://www.overmind-studios.de), it transforms Fusion into a pipeline-aware environment, ensuring technical consistency and automated organization across the entire production.

<img src="images/screenshot.png" alt="Ramses-Fusion Interface" width="25%">

## 🌟 Overview

Ramses-Fusion integrates the production database directly into the Fusion interface. It removes the need for manual file system management by enforcing project standards at the software level. Every composition is synchronized with the database, ensuring that versions are tracked, technical specifications are met, and renders are delivered to the correct locations automatically.

## 🚀 Key Capabilities

### 🔗 Pipeline Integration & Browsing
The tool provides a centralized interface to browse projects, sequences, and shots. 
* **Shot Switching:** Quickly jump between shots or initialize new compositions using standardized templates.
* **Context Awareness:** The UI dynamically tracks your current Project, Shot, and Step (task), providing relevant shortcuts for your specific context.

### 📐 Automated Scene Configuration
Standardize your working environment with a single click. The **Setup Scene** function pulls technical specifications directly from the Ramses database to configure:
* **Format:** Resolution, Pixel Aspect Ratio, and Framerate.
* **Frame Range:** Global and Render ranges are automatically aligned with shot durations.
* **Render Anchors:** Automatically generates managed `_PREVIEW` and `_FINAL` Saver nodes. These anchors are pre-configured with the correct server paths and codecs (ProRes), so you never have to manually name a render file.

### 📦 Asset & Version Management
Manage the flow of data into your composition without browsing folders.
* **Smart Importing:** Bring in published renders or assets with automated node naming and frame-start alignment.
* **Version Swapping:** Replace existing Loader nodes with new versions or different assets while maintaining all downstream node connections.
* **Retrieval:** Instantly access and restore previous versions of your composition directly from the versioning archive.

### 🏁 Technical Validation & Publishing

The tool acts as a gatekeeper to ensure only technically correct data moves down the pipeline.

* **Mismatch Detection:** Before publishing, the tool validates your composition's resolution, FPS, and frame range against the database, warning you of any discrepancies.

* **Automated Publishing:** Handles the archival of the `.comp` file and the rendering of master files in one step.

* **Metadata Logging:** Every save and publish can be accompanied by comments that are logged directly into the Ramses database for production tracking.

## 🛠️ Roadmap / TODO

* **Configurable Codecs:** Currently, the output codecs for `_PREVIEW` (ProRes 422) and `_FINAL` (ProRes 4444) are hardcoded. Future updates will allow these to be configured via the **Ramses Project Settings** to ensure consistency across the entire pipeline.

*Developed with ε> by [Overmind Studios](https://www.overmind-studios.de).*
