# Ramses-Fusion

**Ramses-Fusion** is a bridge between the [Ramses](https://ramses.rxlab.guide/) pipeline ecosystem and Blackmagic Fusion. Developed by [**Overmind Studios**](https://www.overmind-studios.de), it transforms Fusion into a pipeline-aware environment, ensuring technical consistency and automated organization across the entire production.

<img src="images/screenshot.png" alt="Ramses-Fusion Interface" width="25%">

## 🌟 Overview

Ramses-Fusion integrates your production database directly into the Fusion interface. It removes the need for manual file management by enforcing project standards automatically. Every composition is synchronized with the database, ensuring that versions are tracked, technical specifications are met, and renders are delivered to the correct locations without manual intervention.

## 🚀 Key Capabilities

### 🔗 Pipeline Integration & Browsing
The tool provides a centralized interface to navigate your project structure.
* **Smart Navigation:** Quickly jump between shots or initialize new compositions using standardized studio templates.
* **Context Awareness:** The UI dynamically tracks your active task, providing relevant shortcuts and information for your specific shot.

### 📐 Automated Scene Configuration
Standardize your working environment with a single click. The tool pulls technical specifications from the database to configure your scene:
* **Project Alignment:** Automatically sets resolution, framerate, and aspect ratio.
* **Frame Accuracy:** Aligns the timeline and render ranges with the shot duration defined in the pipeline.
* **Managed Render Anchors:** Generates specialized nodes that handle all output paths and render settings automatically, ensuring you never have to manually name a file.

### 📦 Asset & Version Management
Manage the flow of data into your composition without browsing folders.
* **Smart Importing:** Bring in published renders or assets with automated naming and alignment.
* **Version Control:** Easily swap existing assets for newer versions or different iterations while maintaining your node connections.
* **Retrieval:** Instantly access and restore previous versions of your work from the production archive.

### 🏁 Validation & Publishing
The tool acts as a gatekeeper to ensure only technically correct data moves down the pipeline.
* **Mismatch Detection:** Before delivery, the tool verifies your composition against project standards and warns you of any discrepancies.
* **Safe Publishing:** Orchestrates the archival of your composition and the rendering of master files in one step. The process ensures that the database and the server stay perfectly in sync.
* **Production Tracking:** All progress and comments are logged directly into the database for transparent production tracking.

*Developed with ε> by [Overmind Studios](https://www.overmind-studios.de).*