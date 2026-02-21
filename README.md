<p align="right">
  <img src="https://img.shields.io/github/v/release/MoMo830/AliG?style=for-the-badge&color=orange" alt="Version">
  <img src="https://img.shields.io/github/downloads/MoMo830/AliG/total?style=for-the-badge&color=blue&cache=0" alt="Total Downloads">
</p>


# A.L.I.G. - Advanced Laser Imaging Generator 
*Project born on February 5, 2026. Still alive and laser-focused.*



<p align="center">
  <img src="Ressources/ALIG_Anim.gif" alt="A.L.I.G. Interface Demo" width="95%">
  <br>
  <a href="https://buymeacoffee.com/momo830"><img src="https://img.shields.io/badge/Donate-Buy%20Me%20A%20Coffee-orange?style=flat-square&logo=buy-me-a-coffee" alt="Support the project"></a>
</p>



## Description
### A high-precision CAM dedicated to advanced raster engraving and hardware calibration.
ALIG gives you **total control** over the G-Code generation process. Whether you are using a standard hobbyist controller or a professional industrial setup, you can fine-tune every parameter to match your hardware's response.

* **Universal Compatibility**: Supports standard **S (Spindle)** commands for GRBL, Marlin, and FluidNC, as well as high-speed **M67 (Analog)** commands for Mach4/PoKeys57CNC systems.
* **Smart File Optimization**: Built-in **Grayscale Clustering** and quantization (2-256 steps) to drastically reduce G-Code size and ensure jitter-free motion.
* **Hardware Calibration**: Adjust laser latency (ms), overscan, and power curves (Gamma/Contrast) with a real-time visual preview.
* **Portable**: Standalone executable—no Python installation required.

## How to Download & Run

**Configuration Safety**: If you updated your version and encounter errors, rename your previous `alig_config.json` in order to avoid **conflicts with new configuration keys**. This will allow the software to generate a fresh, compatible settings file on the next launch.

[![GitHub release](https://img.shields.io/github/v/release/MoMo830/ALIG?label=Latest%20Version&color=orange)](https://github.com/MoMo830/ALIG/releases/latest)  
If you just want to use the software without installing Python, follow these steps:

1.  Look at the **"Releases"** section on the right side of this page.
2.  Click on the latest version.
3.  Under **Assets**, download the `.exe` file.
    * *Note: Do NOT use the "Download ZIP" green button at the top, as it only contains the source code.*
4.  Run the `.exe` on your Windows machine. No installation is required.
5.  Note that the last configuration used is automatically saved via `alig_config.json` in the same folder of the exe file.

## Last version change 
### (18/02/2026) **v0.9781b** :
- **Real G-Code Parser Simulation**: Re-engineered the simulation engine to process actual G-Code commands for 100% fidelity between preview and final laser output.
- **Interactive Dashboard**: Added a new landing page featuring usage statistics (total lines, G-Code generated).
- **Project Thumbnails**: Implemented automatic generation of visual previews for every processed G-Code, stored in an optimized thumbnail gallery.
- **Machine Calibration Suite**: Introduced a dedicated calibration view with built-in tests for laser latency (alignment) and power scaling grids.
- **Advanced Settings Page**: Added a new configuration interface to manage machine parameters and UI themes without editing JSON files manually.
- **UI/UX Overhaul**: Completely redesigned the TopBar and navigation flow for smoother transitions between Raster, Calibration, and Dashboard views.
- **Internationalization (i18n)**: Initial support for multi-language handling (English/French) to prepare for global community use.


<details>
<summary><b> Click to view full version history</b></summary>


### (14/02/2026)
* **v0.9781b** : Modular Architecture: Split project into core/ and gui/ folders; New Loupe Feature: Added interactive magnifying glass (hold left-click); UI Improvements: Refined control panel layout.
### (12/02/2026)
* **v0.978b** : Added Simulation window with real-time stats; Fixed overscan/burn issues via "Overscan Chopping" for frequent M67 refreshes; Enhanced Safety Protocol using G4 "Safety Flushes" before rapid moves
* **v0.9771b** : Fixed DPI calculation based on line step and suppressed x-resolution parameter.  
### (11/02/2026)
* **v0.977b** : Added Grayscale Steps & G-Code Clustering Features: Users can now select the number of power quantization levels (2-256) reducing .nc file size and prevents controller buffer overflow.
* **v0.976b** : Added Pointing Features: Users can now include a dedicated "Pointing Command" at the origin anchor point. This ensures precise physical alignment of the laser head before the engraving process begins.
* **v0.975b** : Added matrix inversion for deep engraving, strict input validation, and dynamic UI feedback on the G-code generation button.
* **v0.974b** : Added "Force width" parameter to automatically adapt the X-step / Rationalized internal logic for settings storage and profile exportation.
* **v0.973b** : Added firing mode selection (M3/M4), fixed framing logic & UI, optimized graphic performance and image/output folder UI.
### (10/02/2026)
* **v0.972b** : Added optional integrated framing with customizable pause commands (M0/M1)
* **v0.971b** : Added **DPI input field** / **Controller Max Value** / **Import / Export** of configuration profiles.
* **v0.97b** : Added Calibration tools (generation of two patterns to help calibrate settings).
* **v0.96b** : Added custom origin point / frame check option.
* **v0.94b** : Added analog ouput choice for M67 and S support.
* **v0.93b** : Origin selection added / improved display.
### (08/02/2026)
* **v0.92b** : Switched pre-moves from **G0 to G1** to ensure a constant velocity and eliminate the sawtooth effect on the image edges.

</details>


## Roadmap

### Phase 1: Core Stability & UX (Towards v1.0)
* **Comprehensive Raster Toolkit:** Finalizing the entire user interface to provide a rock-solid, streamlined environment dedicated to high-performance rastering.
* **Latency Visual Correction:** Implement a toggle option to mathematically compensate for hardware latency in the simulation view (visual correction only), ensuring a perfectly aligned preview. (done)
* **Export Policy Overhaul:** Flexible export management allowing users to choose specific file extensions (e.g., .gcode, .nc, .txt) to match various CNC controller requirements.
* **Code Consolidation & Stress Testing:** Heavy workload testing to ensure 100% stability on massive G-code files.
* **UI Enhancement & Custom Branding:** * Replace emojis with custom SVG vector icons (Theme-aware).
    * Dynamic color adaptation for seamless Light/Dark mode transitions.
* **Full Internationalization (i18n):** Completion of multi-language support for the entire interface.
* **Onboarding Experience:** First-run setup wizard for essential machine configuration (safety limits, workspace, language).
* **Variable Raster Direction:** X-axis or Y-axis engraving optimization.
* **Async Streamed Parsing:** Implement a buffered G-code processing system to allow real-time simulation rendering while the generation is still in progress (eliminating UI freezing on large files).

---
##  Milestone: Version 1.0 (Official Stable Release)
**Goal:** Providing a rock-solid, theme-responsive tool for high-quality rastering and universal 2D G-code processing with advanced visual feedback.
---

### Phase 2: Advanced Features & Post-1.0
* **Universal 2D G-code Parser & Preview:** Full implementation of the G-code parser with a built-in trajectory visualizer to support and clean any standard 2D G-code file.
* **Smart Calibration Analysis:** Implementation of a computer vision module to analyze user-uploaded photos of calibration tests. The system will automatically suggest parameter corrections (latency) based on visual results.
* **Interactive Workspace Navigation:** Enhanced visualization tools including Real-time Zoom and Pan (drag-to-move) to inspect high-resolution G-code paths.
* **Large File Management:** Option to split massive G-code files for better buffer management.
* **[Likely] Dithering Implementation:** Integration of the Floyd-Steinberg algorithm for superior grayscale rendering.
* **[Under consideration] Auto-Contour Detection & Trace:** Automatic edge tracing to generate vector-like boundaries with support for hatch filling.
* **[Under consideration] Diagonal Rastering (45°):** Advanced trajectory logic to engrave at 45-degree angles.
* **[Theoretical] Hybrid Engine:** Implementation of SVG path parsing to allow hybrid projects (Raster engraving + Vector cutting) in a single G-code file.
* **[In discussion] 3D Relief Engraving Mode:** Implementation of multi-pass logic with Z-axis decrement for deep carving. *Currently seeking user feedback/interest due to hardware power constraints.*

---

## Support & Contributions
A.L.I.G. is a free project, developed during their spare time by a world-class team of... just me. If this tool has helped you with your CNC projects or saved you time, please consider supporting its development. Your contributions help cover the costs of testing materials and hardware for further compatibility tests.

* **Donations:** [Support A.L.I.G. on Buy Me a Coffee](https://buymeacoffee.com/momo830)
* **Feedback:** If you encounter any issues or have suggestions for new features, feel free to open an **Issue**.

**Author:** Alexandre "MoMo"

---

## ⚠️ WARNING & SAFETY DISCLAIMER
> [!CAUTION]
> **ALIG is a G-code generator (CAM).** It does not control your machine.
>
> Laser engraving involves real physical risks. Always:
> - Wear certified safety goggles
> - Verify your machine is in Laser Mode
> - Check overscan travel limits
> - Inspect generated G-code before execution
>
> Full safety documentation is available in the Wiki.




      



 




