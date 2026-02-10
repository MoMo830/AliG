 <p align="right">

  <img src="https://img.shields.io/github/v/release/MoMo830/AliG?style=for-the-badge&color=orange" alt="Version">

  <img src="https://img.shields.io/github/downloads/MoMo830/AliG/total?style=for-the-badge&color=blue" alt="Total Downloads">

</p>


# A.L.I.G. - Advanced Laser Imaging Generator 




<p align="center">
  <img src="assets/screen_alig_0.971b.jpg" alt="AMC" width="80%">
  <br>
  <a href="https://buymeacoffee.com/momo830"><img src="https://img.shields.io/badge/Donate-Buy%20Me%20A%20Coffee-orange?style=flat-square&logo=buy-me-a-coffee" alt="Support the project"></a>
</p>



## Description
A specialized G-Code generator for grayscale laser engraving.
Originally developed for Mach4/PoKeys57CNC using M67 commands, it now supports standard S commands as well. This application is bundled with PyInstaller as a standalone executable, requiring no Python installation to run.

## Last version change 
* **v0.972b** : Added optional integrated framing with customizable pause commands (M0/M1) (!!warning!! laser might still be on during pause or with no M3 after the pause, Work in progress)
* **v0.971b** : Added **DPI input field** / **Controller Max Value** / **Import / Export** of configuration profiles.
* **v0.97b** : Added Calibration tools (generation of two patterns to help calibrate settings).
* **v0.96b** : Added custom origin point / frame check option.
* **v0.94b** : Added analog ouput choice for M67 and S support.
* **v0.93b** : Origin selection added / improved display.
* **v0.92b** : Switched pre-moves from **G0 to G1** to ensure a constant velocity and eliminate the sawtooth effect on the image edges.

## Roadmap :
* Framing Refinement: Implementation of safety pauses and synchronization.
* G-Code Command Abstraction (Decoupling machine configuration (Header/Footer) from functional laser commands).
* File Management Improvements: Better path handling and profile persistence.
* Greyscale Depth Maps: Support for 3D relief engraving (Inversion and contrast optimization for depth control).
* Option for auto-homing at start.
* (maybe) Dithering Implementation: Integration of the Floyd-Steinberg algorithm.
* (maybe) Auto-Contour Detection & Trace & Fill Logic: Automatic edge tracing to generate vector-like boundaries with support for hatch filling.

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

### X-resolution scale
The X-resolution scale reduces the resolution along the X-axis in order to reduce the controller workload and reach the desired feedrate. To maintain a feedrate of 3000mm/min, a value of **1.2** is sufficient for my setup.

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
A.L.I.G. is a free, personal project developed during my spare time. If this tool has helped you with your CNC projects or saved you time, please consider supporting its development. Your contributions help cover the costs of testing materials and hardware for further compatibility tests.

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
> **OVERSCAN CALCULATION:** The "X-resolution scale" and "Premove" features affect the total travel distance of your laser head.
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
 
## How to Download & Run

**Configuration Safety**: If you updated your version and encounter errors, rename your previous `alig_config.json` in order to avoid **conflicts with new configuration keys**. This will allow the software to generate a fresh, compatible settings file on the next launch.
  
If you just want to use the software without installing Python, follow these steps:

1.  Look at the **"Releases"** section on the right side of this page.
2.  Click on the latest version (e.g., `v0.971b`).
3.  Under **Assets**, download the `.exe` file (e.g., `ALIG_v0.971b.exe`).
    * *Note: Do NOT use the "Download ZIP" green button at the top, as it only contains the source code.*
4.  Run the `.exe` on your Windows machine. No installation is required.
5.  Note that the last configuration used is automatically saved via `alig_config.json` in the same folder of the exe file.



