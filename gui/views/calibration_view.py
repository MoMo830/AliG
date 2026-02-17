import customtkinter as ctk
import tkinter as tk
import os
from PIL import Image, ImageDraw
from core.utils import get_app_paths

class CalibrationView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.base_path, self.application_path = get_app_paths()
        
        # --- HEADER ---
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=40, pady=(30, 20))
        
        
        ctk.CTkLabel(self.top_frame, text="MACHINE CALIBRATION", 
                     font=("Arial", 24, "bold"), text_color="#e67e22").pack(side="left", expand=True, padx=(0, 100))

        # --- CONTAINER ---
        self.main_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_container.pack(expand=True, fill="both", padx=40)

        self.setup_calibration_cards()

    def setup_calibration_cards(self):
        # 1. TEST DE LATENCE
        self.create_test_card(
            "LASER LATENCY TEST",
            "Generates a 30x30mm black square to test beam alignment (m67_delay).\nRun this at high speed to check for double lines.",
            "⏱️",
            self.run_latency_test
        )

        # 2. TEST DE PUISSANCE (Grille de dégradé)
        self.create_test_card(
            "POWER SCALE GRID",
            "Generates 10 squares from 0% to 100% power.\nUseful to see how the material reacts to different intensities.",
            "🔥",
            self.run_power_test
        )

    def create_test_card(self, title, desc, icon, callback):
        card = ctk.CTkFrame(self.main_container, fg_color=["#F2F2F2", "#2B2B2B"], border_width=1)
        card.pack(fill="x", pady=10, padx=5)
        
        lbl_icon = ctk.CTkLabel(card, text=icon, font=("Arial", 30))
        lbl_icon.pack(side="left", padx=20, pady=20)
        
        txt_frame = ctk.CTkFrame(card, fg_color="transparent")
        txt_frame.pack(side="left", fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(txt_frame, text=title, font=("Arial", 16, "bold")).pack(anchor="w")
        ctk.CTkLabel(txt_frame, text=desc, font=("Arial", 12), text_color="gray", wraplength=500, justify="left").pack(anchor="w")
        
        ctk.CTkButton(card, text="PREPARE TEST", width=120, fg_color="#e67e22", hover_color="#d35400",
                      command=callback).pack(side="right", padx=20)

    # --- LOGIQUE DE GÉNÉRATION D'IMAGES ---

    def run_latency_test(self):
        """ Génère un carré noir pur et l'envoie vers RasterView """
        width, height = 30, 30
        img = Image.new('L', (width, height), color=0)
        
        temp_path = os.path.join(self.application_path, "ALIG_LATENCY_TEST.png")
        img.save(temp_path)
        
        # On bascule vers RasterView avec l'image chargée
        self.controller.show_raster_mode(image_to_load=temp_path,reset_filters=True)

    def run_power_test(self):
        """ Génère une grille de dégradé et l'envoie vers RasterView """
        block_size = 50
        num_steps = 10
        padding_x = 5 
        
        width = block_size * num_steps
        height = block_size
        
        img = Image.new('L', (width, height), color=255)
        draw = ImageDraw.Draw(img)

        for i in range(num_steps):
            # Calcul du niveau de gris (noir à gauche, blanc à droite ou inversement)
            gray_level = int(255 - (i * (255 / (num_steps - 1))))
            
            x_start = (i * block_size) + padding_x
            x_end = ((i + 1) * block_size) - padding_x
            draw.rectangle([x_start, 0, x_end, height], fill=gray_level)

        temp_path = os.path.join(self.application_path, "ALIG_POWER_TEST.png")
        img.save(temp_path)
        
        # On bascule vers RasterView avec l'image chargée et des réglages neutres
        self.controller.show_raster_mode(image_to_load=temp_path, reset_filters=True)

    def run_speed_test(self):
        # On pourra implémenter ici une grille multi-vitesse plus tard
        print("Speed test not yet implemented via image.")