<p align="right">
  <img src="https://img.shields.io/github/v/release/MoMo830/AliG?style=for-the-badge&color=orange" alt="Version">
  <img src="https://img.shields.io/github/downloads/MoMo830/AliG/total?style=for-the-badge&color=blue" alt="Total Downloads">
</p>


# A.L.I.G. - Advanced Laser Imaging Generator 
*Project born on February 5, 2026. Still alive and laser-focused.*



<p align="center">
  <img src="assets/ALIG_Anim.gif" alt="A.L.I.G. Interface Demo" width="95%">
  <br>
  <a href="https://buymeacoffee.com/momo830"><img src="https://img.shields.io/badge/Donate-Buy%20Me%20A%20Coffee-orange?style=flat-square&logo=buy-me-a-coffee" alt="Support the project"></a>
</p>



## Description
### A Specialized & Optimized G-Code Generator for Laser Engraving
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
### (12/02/2026)
* **v0.978b** : Added Simulation window with real-time stats; Fixed overscan/burn issues via "Overscan Chopping" for frequent M67 refreshes; Enhanced Safety Protocol using G4 "Safety Flushes" before rapid moves
* **v0.9771b** : Fixed DPI calculation based on line step and suppressed x-resolution parameter.

<details>
<summary><b> Click to view full version history</b></summary>
  
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

## Known issues :
* On low resolution screens or high Windows scaling settings (150%+), some UI elements may be cut off or overlap.

## Roadmap :
* **Code Consolidation & Stress Testing:** Heavy workload testing to ensure 100% stability on massive G-code files.
* **UI/UX Overhaul:** Rationalizing the interface to move away from "slider-heavy" menus towards a more intuitive workflow.
* Option to split big Gcode files?
* Calibration improvement to test and select best settings (power range, thermal correction, latency).
* **Variable Raster Direction:** Toggle between Horizontal (X-axis) and Vertical (Y-axis) engraving. This allows optimizing for machine rigidity or following wood grain patterns.
* [In discussion] 3D Relief Engraving Mode:** Implementation of multi-pass logic with Z-axis decrement for deep carving. *Since my current laser lacks the power to benchmark this properly, I'm looking for user interest/feedback before developing this.*
* [Likely] Dithering Implementation: Integration of the Floyd-Steinberg algorithm.
* [Under consideration] Auto-Contour Detection & Trace & Fill Logic: Automatic edge tracing to generate vector-like boundaries with support for hatch filling.
* [Under consideration] Diagonal Rastering (45°):** Advanced trajectory logic to engrave at 45 degrees. 
* [Theoretical] Implementation of SVG path parsing to allow hybrid projects (Raster engraving + Vector cutting) in a single G-code file.
* Keep this readme up-to-date !
* Add a Wiki.

## Gcode Export
All trajectories are calculated using **Absolute Coordinates**. This ensures that every pixel of the image is tied to a fixed position relative to your origin, preventing cumulative errors or trajectory drift common in incremental modes.

| Parameter | Description | G-Code Command |
| :--- | :--- | :--- |
| **Distance Mode** | **Absolute Positioning** (Fixed precision) | `G90` |
| **Unit System** | Metric (**Millimeters**) | `G21` |
| **Plane Selection** | **X / Y** Working Plane | `G17` |
| **Feedrate Mode** | **Units per Minute** | `G94` |
| **Laser (Analog)** | Real-time synced modulation (Mach4/PoKeys) | `M67 E[0-3] Q[0-XXX]` |
| **Laser (Spindle)** | Universal Spindle command (GRBL/Smoothie) | `S[0-XXX]` |

The final file is exported with the `.nc` extension.

## Parameters
### Line Step / Resolution (mm)
This is the "vertical resolution" of your project. It defines the distance between each horizontal pass of the laser.

* **Optimal Setting:** This value should ideally match your laser's physical beam spot size (typically between **0.1mm and 0.15mm** for most diodes).
* **The Focus Factor:** The ideal setting depends heavily on your **laser focus**. A perfectly focused laser allows for a finer step, while a slightly out-of-focus beam will require a larger step to cover the surface.
* **Too Low:** If the Line Step is too small, the laser passes will overlap excessively. This results in a **much darker image**, loss of detail, and potential over-charring of the wood fibers due to accumulated heat.
* **Too High:** If the Line Step is too large, you will see **visible gaps or white "striped" zones** between the passes where the material remains unmarked, leading to a faded and inconsistent result.
  
### DPI (Dots Per Inch)
This parameter defines the horizontal resolution of your engraving. While the Line Step controls the vertical spacing between passes, the DPI determines how many individual laser pulses occur along each horizontal line.
* X-Axis Resolution: Adjusting the DPI directly changes the density of points on the X-axis. A higher DPI results in more concentrated laser pulses per inch, increasing the level of horizontal detail.
* Risk of Overloading: Be cautious with excessively high values. A DPI that exceeds your laser's physical capabilities or the material's thermal threshold can overload the engraving area, leading to excessive heat buildup and a charred appearance.
* Hardware Limitations: Beyond the material, an extremely high DPI can overload the controller board. Forcing the processor to handle too many instructions per second may cause "stuttering," buffer underuns, or communication timeouts, potentially ruining the job. It also significantly increases processing time without necessarily improving visual quality.

### Thermal Correction
The Thermal Correction setting adjusts the power ramp of your laser. By increasing this coefficient, you slow down the power rise, keeping the laser at lower intensities for a longer range of gray tones. This prevents premature wood carbonization and preserves subtle details in highlights and mid-tones, ensuring that high power is only reached for the deepest blacks.

### Min Power (%)
Sets the power level for the lightest parts of your image. Since every material (wood types, MDF, etc.) has a different combustion threshold, this setting ensures the laser is already at its "starting point" for the first level of gray, preventing "dead zones" in the highlights.

### Max Power (%)
Defines the upper power limit for the darkest pixels. Adjust this based on your laser's wattage and the material's density. The goal is to achieve a deep black without deep charring or structural damage to the wood fibers.

### Laser latency/delay (ms)
M67 commands and Laser drivers have internal delays. Therefore, there's a parameter to take this into account. In my build, at a feedrate of 3000mm/min, the ideal setting is **11.5 ms**. If this parameter is not correctly set, you will experience blur as the engraved lines will not align.

### Premove /Overscan (mm)
Premove adds an overscan to allow your machine to reach a constant velocity before the laser starts engraving, ensuring consistent power delivery.

---

## Support & Contributions
A.L.I.G. is a free project, developed during their spare time by a world-class team of... just me. If this tool has helped you with your CNC projects or saved you time, please consider supporting its development. Your contributions help cover the costs of testing materials and hardware for further compatibility tests.

* **Donations:** [Support A.L.I.G. on Buy Me a Coffee](https://buymeacoffee.com/momo830)
* **Feedback:** If you encounter any issues or have suggestions for new features, feel free to open an **Issue**.

**Author:** Alexandre "MoMo"

---

## ⚠️ WARNING & SAFETY DISCLAIMER

> [!CAUTION]
> **NOT A CONTROL SOFTWARE:** This application is a **G-Code Generator (CAM)**. It does not connect to or control your CNC machine directly. It is designed to process images and export `.nc` files. You must use a dedicated controller software (like Mach4, UGS, or LaserGRBL) to run the generated files.
> 
> **LASER SAFETY:** This software generates G-Code utilizing `M3` by default and `M67/S` commands. **`M3` is used to arm the laser**, but on certain CNC configurations, it may trigger a spindle motor instead.
> 
> **HARDWARE COMPATIBILITY:** Always verify your G-Code and ensure your controller is explicitly set to **Laser Mode** before execution. Use this program at your own risk. The author assumes no liability for hardware damage or personal injury.
> 
> **BETA SOFTWARE:** This application is currently in **Beta**. While it has been tested, bugs may still exist. **Always perform a manual inspection of the generated G-Code text** (check for unexpected values or command syntax) before running it on your CNC machine.

### Work Area & Premove Warning

> [!IMPORTANT]
> **OVERSCAN CALCULATION:** The “Premove” feature affects the total travel distance of your laser head.
> * **Premove:** Adds an overscan distance (default 15mm) to both sides of your image. 
> * **Example:** If your image is 100mm wide with a 15mm premove, the laser head will travel **130mm** in total.
> * **Action Required:** Ensure your machine's physical travel limits (Soft/Hard Limits) can accommodate this extra width to avoid crashing into the frame. Always perform a "frame" or "boundary" check.

### Operational Rules
* **Always wear certified laser safety goggles** matching your laser's wavelength.
* **Check your work surface:** Ensure the material is flat and the extended travel path is clear of obstacles.
* **Never leave the machine unattended** while the laser is active.
* **Verify Emergency Stop:** Ensure your E-Stop is functional and within reach before starting any job.
* **Ventilation:** Ensure proper air extraction; laser engraving can produce toxic fumes depending on the material.

---

##  Infos, Tips & Tuning
This software is intended to be used on a CNC machine. I developped it as a desire to expand the capabilities of my Workbee/Queenbee based CNC. 

<p align="center">
  <img src="assets/AMC.jpg" alt="AMC" width="50%">
</p>

* **Workflow Efficiency:** I used to work with **Auggie**, which is a functional solution, but I found it difficult to constantly switch **back and forth** between it and Mach4. A.L.I.G. allows for a more streamlined workflow within a single ecosystem.
* **Speed and Responsiveness (Q vs S):** In Mach4, the standard `S` command (Spindle speed) is often processed too slowly for high-speed laser engraving, leading to stuttering or "blobs" in the image. A.L.I.G. uses the **`Q` parameter** (mapped to a PWM Analog Output) because it is processed instantly by the motion controller, ensuring synchronized power changes at high feed rates.


* **Software version used:**
   * MACH4 : build 6693
   * Pokeys plugin : 9.17.0.5596
* **Software Settings (Mach4/PoKeys):**
    * In the PoKeys plugin settings (**Configure > Plugins > PoKeys > Miscellaneous**), ensure your PWM pin box is checked and set **Spindle Control** to "None".
    * In the Mach4 Analog Output settings:
        * Map **Analog Output 0** to your device name (**PoKeys_XXXXX**).
        * Select the correct **PWM Duty** (corresponding to your hardware PWM pin).
        * **Crucially:** Set both the **Numerator and Denominator to 1**, and leave the **Offset at 0**.

* **Z-Axis & Focus:** Please note that **A.L.I.G. does not command any Z-axis movement.** * You **must** manually set your laser focus and your Z-zero position prior to starting the job. 
    * Ensure your laser is at the optimal height for your material, as the generated G-code only manages X, Y, and Q/S (power) parameters.
      
* **PWM Frequency:** Depending on your motion controller and laser driver, you should experiment to find the optimal PWM frequency. For instance, I originally used 20 kHz but struggled to achieve a full range of grayscale. Lowering the frequency to **5000 Hz** significantly improved the laser's response and the subtlety of the gradients.

* **Dedicated Mach4 Profile:** It is highly recommended to create a **separate profile** in Mach4 specifically for laser engraving. 
    * This prevents laser settings (like PWM mapping and Spindle-to-None configuration) from interfering with your standard milling/routing setups.
    * It allows you to fine-tune your motor acceleration and velocity for laser work without affecting your heavy-duty milling parameters.
 




