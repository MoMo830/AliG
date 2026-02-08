# A.L.I.G. - Advanced Laser Imaging Generator

![Aperçu de l'interface](assets/screen_alig.jpg)

## Description
A specialized G-Code generator for grayscale laser engraving using Mach4/PoKeys57CNC and M67 commands. This application is bundled with PyInstaller as a standalone executable, requiring no Python installation to run.

## Last version change (v0.92b)
Switched pre-moves from **G0 to G1** to ensure a constant velocity and eliminate the sawtooth effect on the image edges.

![Aperçu de l'interface](assets/v0.92b.png)
*Patterned vertical lines on X-axis. Likely mechanical vibration, PWM interference or image resolution conflict. If someone has the same artifacts, please let me know.*

## Parameters

### Delay Compensation
M67 commands and Laser drivers have internal delays. Therefore, there's a parameter to take this into account. In my build, at a feedrate of 3000mm/min, the ideal setting is **11.5 ms**. If this parameter is not correctly set, you will experience blur as the engraved lines will not align.

### Thermal Correction
The Thermal Correction setting adjusts the power ramp of your laser. By increasing this coefficient, you slow down the power rise, keeping the laser at lower intensities for a longer range of gray tones. This prevents premature wood carbonization and preserves subtle details in highlights and mid-tones, ensuring that high power is only reached for the deepest blacks.

### X_step Multiplier
The X_step Multiplier reduces the resolution along the X-axis in order to reduce the controller workload and reach the desired feedrate. To maintain a feedrate of 3000mm/min, a value of **1.2** is sufficient for my setup.

### Premove (Overscan)
Premove adds an overscan to allow your machine to reach a constant velocity before the laser starts engraving, ensuring consistent power delivery.

## Miscellaneous
* The last configuration used is automatically saved via `alig_config.json`.

---

## Support & Contributions
If you encounter any issues or have suggestions, feel free to open an **Issue**.

**Author:** Alexandre "MoMo"

---

## ⚠️ WARNING & SAFETY DISCLAIMER

> [!CAUTION]
> **LASER SAFETY:** This software generates G-Code utilizing `M3` and `M67` commands. **`M3` is used to arm the laser**, but on certain CNC configurations, it may trigger a spindle motor instead.
> 
> **HARDWARE COMPATIBILITY:** Always verify your G-Code and ensure your controller is explicitly set to **Laser Mode** before execution. Use this program at your own risk. The author assumes no liability for hardware damage or personal injury.

### Work Area & Premove Warning

> [!IMPORTANT]
> **OVERSCAN CALCULATION:** The "Premove" feature adds an **overscan distance** (default 15mm) to both sides of your image. 
> * **Example:** If your image is 100mm wide with a 15mm premove, the laser head will travel **130mm** in total.
> * **Action Required:** Ensure your machine's physical travel limits (Soft Limits/Hard Limits) can accommodate this extra width to avoid crashing into the frame. Always perform a "frame" or "boundary" check before firing.

### Operational Rules
* **Always wear certified laser safety goggles** matching your laser's wavelength.
* **Check your work surface:** Ensure the material is flat and that the extended travel path (including overscan) is clear of obstacles.
* **Never leave the machine unattended** while the laser is active.
* **Verify that your emergency stop is functional** before starting any job.
