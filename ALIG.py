# -*- coding: utf-8 -*-
"""
A.L.I.G. - Advanced Laser Imaging Generator
===========================================
Version: 0.92b
Author: Alexandre "MoMo"
License: MIT
Description: 
    Specialized G-Code generator for grayscale laser engraving. 
    Optimized for Mach4 and PoKeys57CNC using M67 analog commands.
    Features: Constant velocity pre-moves (overscan), Gamma & Thermal 
    correction, and real-time power distribution preview.

GitHub: https://github.com/MoMo830/ALIG
"""



import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys
import json
import os

ctk.set_appearance_mode("Dark")

class LaserGeneratorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.version = "0.92b"
        self.title(f"A.L.I.G. - Advanced Laser Imaging Generator v{self.version}")
        self.geometry("1600x1050")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))

        self.config_file = os.path.join(application_path, "alig_config.json")
        self.input_image_path = ""
        self.output_dir = application_path
        
        self.controls = {}
        self.setup_ui()
        self.load_settings() 
        self.update_preview()

    def on_closing(self):
        self.save_settings()
        plt.close('all')
        self.destroy()
        sys.exit()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SIDEBAR ---
        self.sidebar = ctk.CTkScrollableFrame(self, width=380)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(self.sidebar, text=f"A.L.I.G. SETTINGS v{self.version}", font=("Arial", 16, "bold")).pack(pady=(5, 10))

        file_frame = ctk.CTkFrame(self.sidebar, fg_color="#333333")
        file_frame.pack(fill="x", padx=10, pady=5)
        
        self.btn_input = ctk.CTkButton(file_frame, text="SELECT IMAGE", fg_color="#444444", command=self.select_input)
        self.btn_input.pack(fill="x", padx=5, pady=5)
        
        self.btn_output = ctk.CTkButton(file_frame, text="SELECT OUTPUT DIR", fg_color="#444444", command=self.select_output)
        self.btn_output.pack(fill="x", padx=5, pady=5)

        # Paramètres principaux
        self.create_input_pair("Target Width (mm)", 5, 400, 30.0, "width")
        self.create_input_pair("Line Step / Resolution (mm)", 0.01, 1.0, 0.1307, "line_step", precision=4)
        
        self.label_real_dim = ctk.CTkLabel(self.sidebar, text="Real dimension: 0 x 0 mm", font=("Arial", 10, "italic"), text_color="#aaaaaa")
        self.label_real_dim.pack(pady=(0, 5))

        self.create_input_pair("Feedrate (F)", 500, 8000, 3000, "feedrate", is_int=True)
        self.label_time_est = ctk.CTkLabel(self.sidebar, text="Estimated Time: --", font=("Arial", 11, "bold"), text_color="#3a9ad9")
        self.label_time_est.pack(pady=(0, 10))

        self.create_input_pair("Contrast (-1.0 to 1.0)", -1.0, 1.0, 0.0, "contrast")
        self.create_input_pair("Gamma Correction", 0.1, 6.0, 1.0, "gamma")
        self.create_input_pair("Thermal Correction", 0.1, 3.0, 1.5, "thermal")

        self.create_input_pair("Min Power (Q)", 0, 100, 10.0, "min_p")
        self.create_input_pair("Max Power (Q)", 0, 100, 40.0, "max_p")
        self.create_input_pair("x_step Multiplier", 0.5, 5.0, 1.2, "x_mult") 
        self.create_input_pair("M67 Delay (ms)", 0, 100, 11.5, "m67_delay")
        self.create_input_pair("Premove (mm)", 0, 30, 10, "premove", is_int=True)

        ctk.CTkLabel(self.sidebar, text="G-Code Footer (before M30):", font=("Arial", 11)).pack(anchor="w", padx=15, pady=(10, 0))
        self.txt_footer = ctk.CTkTextbox(self.sidebar, height=60, font=("Consolas", 11))
        self.txt_footer.pack(fill="x", padx=15, pady=5)
        self.txt_footer.insert("1.0", "M5\nM334\nG4 P2")

        self.btn_gen = ctk.CTkButton(self.sidebar, text="GENERATE G-CODE", fg_color="#1f538d", height=45, font=("Arial", 13, "bold"), command=self.generate_gcode)
        self.btn_gen.pack(pady=20, padx=20, fill="x")
        # À la fin de ton setup_ui, après le bouton GENERATE G-CODE
        ctk.CTkLabel(self.sidebar, text="Developed by Alexandre 'MoMo'", 
        font=("Arial", 10), text_color="#666666").pack(pady=(10, 5))

        # --- VIEWPORT (CORRIGÉ POUR CENTRAGE) ---
        self.view_frame = ctk.CTkFrame(self)
        self.view_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.view_frame.grid_columnconfigure(0, weight=1)
        self.view_frame.grid_rowconfigure(0, weight=1)

        self.fig = plt.figure(figsize=(8, 9), facecolor='#1e1e1e')
        self.gs = self.fig.add_gridspec(2, 1, height_ratios=[4, 1])
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.view_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="")

    def create_input_pair(self, label_text, start, end, default, key, is_int=False, precision=2):
        frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        frame.pack(fill="x", pady=2, padx=10)
        ctk.CTkLabel(frame, text=label_text, font=("Arial", 11)).pack(anchor="w")
        
        sub_frame = ctk.CTkFrame(frame, fg_color="transparent")
        sub_frame.pack(fill="x")
        
        steps = (end - start) if is_int else 200
        slider = ctk.CTkSlider(sub_frame, from_=start, to=end, number_of_steps=steps, 
                                command=lambda v: self.sync_from_slider(slider, entry, v, is_int, precision))
        slider.set(default)
        slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        entry = ctk.CTkEntry(sub_frame, width=65, height=22, font=("Arial", 10))
        format_str = f"{{:.{precision}f}}"
        entry.insert(0, str(int(default)) if is_int else format_str.format(default))
        entry.pack(side="right")
        
        self.controls[key] = {"slider": slider, "entry": entry, "is_int": is_int, "precision": precision}
        
        entry.bind("<Return>", lambda e: self.sync_from_entry(slider, entry, is_int, precision))
        entry.bind("<FocusOut>", lambda e: self.sync_from_entry(slider, entry, is_int, precision))
        return self.controls[key]

    def get_val(self, ctrl):
        val = ctrl["slider"].get()
        return int(val) if ctrl["is_int"] else float(val)

    def select_input(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")])
        if path:
            self.input_image_path = path
            self.update_preview()

    def select_output(self):
        path = filedialog.askdirectory()
        if path: self.output_dir = path

    def process_logic(self):
        tw = self.get_val(self.controls["width"])
        l_step_val = self.get_val(self.controls["line_step"])
        gamma_val = self.get_val(self.controls["gamma"])
        contrast = self.get_val(self.controls["contrast"])
        thermal = self.get_val(self.controls["thermal"])
        min_p = self.get_val(self.controls["min_p"])
        max_p = self.get_val(self.controls["max_p"])
        x_mult = self.get_val(self.controls["x_mult"])

        x_step = l_step_val * x_mult

        if not self.input_image_path or not os.path.exists(self.input_image_path):
            return None, 0, 0, l_step_val, x_step, 0

        img = Image.open(self.input_image_path).convert('L')
        w_px = int(tw / x_step)
        orig_w, orig_h = img.size
        h_px = int((tw * orig_h / orig_w) / l_step_val)
        img = img.resize((w_px, h_px), Image.Resampling.LANCZOS)
        
        arr = 1.0 - (np.array(img, dtype=np.float32) / 255.0)
        if contrast != 0:
            f = (259 * (contrast + 1.0)) / (255 * (259 - contrast)) * 255
            arr = np.clip(f * (arr - 0.5) + 0.5, 0, 1)
        arr = np.power(arr, gamma_val)
        arr = np.power(arr, thermal) 
        matrix = min_p + (arr * (max_p - min_p))
        matrix = np.where(arr < 0.005, 0, np.maximum(matrix, min_p))

        # Calcul temps
        total_dist = h_px * (tw + (2 * self.get_val(self.controls["premove"])))
        feedrate = self.get_val(self.controls["feedrate"])
        est_min = total_dist / feedrate
        
        return matrix, h_px, w_px, l_step_val, x_step, est_min

    def update_preview(self):
        try:
            matrix, h_px, w_px, l_step, x_st, est_min = self.process_logic()
            self.fig.clear()
            
            if matrix is None: 
                self.canvas.draw()
                return
            
            real_w = w_px * x_st
            real_h = h_px * l_step
            self.label_real_dim.configure(text=f"Dimension: {real_w:.2f} x {real_h:.2f} mm")
            
            # Formatage temps
            total_seconds = int(est_min * 60)
            hh, rem = divmod(total_seconds, 3600)
            mm, ss = divmod(rem, 60)
            self.label_time_est.configure(text=f"Estimated Time: {hh:02d}h {mm:02d}min {ss:02d}s")
            
            # 1. AXE IMAGE (En haut)
            ax_img = self.fig.add_subplot(self.gs[0])
            img_plot = ax_img.imshow(matrix, cmap="gray_r", origin='upper', 
                                    extent=[0, real_w, 0, real_h], aspect='equal')
            
            ax_img.set_title("LASER POWER PREVIEW", color='white', pad=10)
            ax_img.tick_params(colors='#666666', labelsize=8)
            ax_img.set_facecolor('#1e1e1e')
            
            # Colorbar : Utilisation de 'fraction' et 'pad' pour minimiser le décalage
            cbar = self.fig.colorbar(img_plot, ax=ax_img, fraction=0.046, pad=0.04)
            cbar.ax.tick_params(labelcolor='white', labelsize=7)

            # 2. AXE HISTOGRAMME (C'est ici que ça manquait)
            ax_hist = self.fig.add_subplot(self.gs[1])
            data_nonzero = matrix[matrix > 0]
            if data_nonzero.size > 0:
                ax_hist.hist(data_nonzero, bins=100, color='#3a9ad9', alpha=0.7)
            
            ax_hist.set_title("Power Distribution (Q)", color='white', fontsize=10)
            ax_hist.set_xlabel("Power", color='#888888', fontsize=8)
            ax_hist.set_ylabel("Pixels", color='#888888', fontsize=8)
            ax_hist.tick_params(colors='#666666', labelsize=8)
            ax_hist.set_facecolor('#1a1a1a')

            # --- AJUSTEMENT POUR LE CENTRAGE ---
            # Pour compenser la présence de la Colorbar à droite, on augmente la marge de gauche (left)
            # de sorte que le bloc [Image + Colorbar] soit centré dans la zone noire.
            self.fig.subplots_adjust(left=0.18, right=0.92, top=0.92, bottom=0.12, hspace=0.4)
            
            self.canvas.draw()
            
        except Exception as e:
            print(f"Preview Error: {e}")

    def generate_gcode(self):
        matrix, h_px, w_px, l_step, x_st, _ = self.process_logic()
        if matrix is None: return
        f_int = self.get_val(self.controls["feedrate"])
        m67_ms = self.get_val(self.controls["m67_delay"])
        offset = (f_int * m67_ms) / 60000 
        pre = self.get_val(self.controls["premove"])

        full_path = os.path.join(self.output_dir, os.path.basename(self.input_image_path).split('.')[0] + ".nc")
        # Dans def generate_gcode(self):
        gcode = [
            f"( A.L.I.G. v{self.version} )",
            f"( Author: Alexandre 'MoMo' )",  # <--- Ajoute cette ligne
            "( Generated for Mach4/PoKeys57CNC )",
            "G21 G90 G17 G94", 
            "M3 M67 E0 Q0"
            ]

        for row_idx in range(h_px):
            y_pos = row_idx * l_step
            py = (h_px - 1) - row_idx 
            is_fwd = (row_idx % 2 == 0)
            
            x_start_img = 0.0 if is_fwd else (w_px - 1) * x_st
            x_end_img = (w_px - 1) * x_st if is_fwd else 0.0
            x_dir = 1 if is_fwd else -1
            corr = offset if is_fwd else -offset
            
            # --- 1. POSITIONNEMENT INITIAL (Saut rapide) ---
            # On se place au point de départ du dépassement
            # row_idx == 0 en G0 pour le confort, les autres en G1 pour la fluidité
            move_cmd = "G0" if row_idx == 0 else "G1"
            gcode.append(f"{move_cmd} X{x_start_img - (pre * x_dir):.3f} Y{y_pos:.4f} F{f_int}")

            # --- 2. PREMOVE EN G1 (Pixels blancs) ---
            # On active M67 Q0 et on avance jusqu'au premier pixel corrigé
            # On utilise ta logique : premier pixel de l'image est à (x_start_img + corr)
            gcode.append(f"M67 E0 Q0 G1 X{x_start_img + corr:.4f}")

            # --- 3. GRAVURE DE L'IMAGE ---
            x_range = range(w_px) if is_fwd else range(w_px - 1, -1, -1)
            for px in x_range:
                # Ta formule exacte : (coordonnée théorique + correction de latence)
                gcode.append(f"M67 E0 Q{matrix[py, px]:.2f} G1 X{(px * x_st) + corr:.4f}")

            # --- 4. POST-MOVE EN G1 (Pixels blancs) ---
            # On éteint et on continue la course pour absorber la décélération
            gcode.append(f"M67 E0 Q0 G1 X{x_end_img + (pre * x_dir):.3f}")

        gcode.append(f"\n{self.txt_footer.get('1.0', tk.END).strip()}\nM30")

        try:
            with open(full_path, "w") as f: f.write("\n".join(gcode))
            messagebox.showinfo("Success", f"G-Code saved to:\n{full_path}")
        except Exception as e: messagebox.showerror("Error", str(e))

    def sync_from_slider(self, slider, entry, value, is_int, precision):
        val = int(float(value)) if is_int else float(value)
        entry.delete(0, tk.END)
        format_str = f"{{:.{precision}f}}"
        entry.insert(0, str(val) if is_int else format_str.format(val))
        self.update_preview()

    def sync_from_entry(self, slider, entry, is_int, precision):
        try:
            val = int(entry.get()) if is_int else float(entry.get())
            slider.set(val)
            entry.delete(0, tk.END)
            format_str = f"{{:.{precision}f}}"
            entry.insert(0, str(val) if is_int else format_str.format(val))
            self.update_preview()
        except: pass

    def save_settings(self):
        data = {k: v["slider"].get() for k, v in self.controls.items()}
        data["input_path"] = self.input_image_path
        data["output_dir"] = self.output_dir
        data["footer"] = self.txt_footer.get("1.0", tk.END).strip()
        try:
            with open(self.config_file, 'w') as f: json.dump(data, f, indent=4)
        except: pass

    def load_settings(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f: data = json.load(f)
                for k, v in data.items():
                    if k in self.controls:
                        precision = self.controls[k].get("precision", 2)
                        self.controls[k]["slider"].set(v)
                        self.controls[k]["entry"].delete(0, tk.END)
                        format_str = f"{{:.{precision}f}}"
                        self.controls[k]["entry"].insert(0, str(int(v)) if self.controls[k]["is_int"] else format_str.format(v))
                self.input_image_path = data.get("input_path", "")
                self.output_dir = data.get("output_dir", self.output_dir)
                if "footer" in data:
                    self.txt_footer.delete("1.0", tk.END)
                    self.txt_footer.insert("1.0", data["footer"])
            except: pass

if __name__ == "__main__":
    app = LaserGeneratorApp()
    app.mainloop()