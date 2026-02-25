# -*- coding: utf-8 -*-
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, 
                             QLabel, QScrollArea, QGridLayout, QPushButton)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon, QFont

from core.translations import TRANSLATIONS
from utils.paths import THUMBNAILS_DIR, ASSETS_DIR

class DashboardViewQt(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        
        # Récupération des textes
        lang = self.controller.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"])["dashboard"]

        # Layout Principal (Horizontal : Gauche = Modes, Droite = Histoire/Stats)
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(30, 20, 30, 20)
        self.main_layout.setSpacing(30)

        # --- COLONNE GAUCHE : MODES (Scrollable) ---
        self.setup_left_column()

        # --- COLONNE DROITE : TITRE + HISTORY + STATS ---
        self.setup_right_column()

    def setup_left_column(self):
        left_container = QFrame()
        left_container.setFixedWidth(420)
        layout = QVBoxLayout(left_container)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        self.modes_layout = QVBoxLayout(content)
        self.modes_layout.setSpacing(15)
        self.modes_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Liste des modes (On réutilise ta logique)
        modes = [
            (self.texts["raster_title"], self.texts["raster_desc"], self.controller.show_raster_mode, "raster_white.png", "normal"),
            (self.texts["calibration_title"], self.texts["calibration_desc"], self.controller.show_calibration_mode, "🔧", "normal"),
            (self.texts["settings_title"], self.texts["settings_desc"], self.controller.show_settings_mode, "⚙️", "normal"),
        ]

        for title, desc, callback, icon, state in modes:
            card = self.create_mode_card(title, desc, callback, icon, state)
            self.modes_layout.addWidget(card)

        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.main_layout.addWidget(left_container)

    def create_mode_card(self, title, desc, callback, icon_data, state):
        card = QFrame()
        card.setObjectName("modeCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor if state == "normal" else Qt.CursorShape.ArrowCursor)
        
        # Style QSS pour simuler le hover de CustomTkinter
        card.setStyleSheet("""
            QFrame#modeCard {
                background-color: #2b2b2b;
                border: 2px solid #3d3d3d;
                border-radius: 15px;
            }
            QFrame#modeCard:hover {
                border-color: #1F6AA5;
                background-color: #333333;
            }
        """)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)

        # Icône (Image ou Emoji)
        icon_label = QLabel()
        if icon_data.endswith(".png"):
            path = os.path.join(ASSETS_DIR, icon_data)
            pix = QPixmap(path).scaled(45, 45, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(pix)
        else:
            icon_label.setText(icon_data)
            icon_label.setFont(QFont("Arial", 25))
        
        layout.addWidget(icon_label)

        # Textes
        text_layout = QVBoxLayout()
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 16px; border: none; background: transparent;")
        d_lbl = QLabel(desc)
        d_lbl.setWordWrap(True)
        d_lbl.setStyleSheet("color: gray; font-size: 12px; border: none; background: transparent;")
        
        text_layout.addWidget(t_lbl)
        text_layout.addWidget(d_lbl)
        layout.addLayout(text_layout)
        layout.setStretch(1, 1)

        # Evenement clic (Qt n'a pas de "command" sur les Frame, on utilise mousePressEvent)
        if state == "normal" and callback:
            card.mousePressEvent = lambda e: callback()

        return card

    def setup_right_column(self):
        right_container = QWidget()
        layout = QVBoxLayout(right_container)
        layout.setContentsMargins(0, 0, 0, 0)

        # Titre A.L.I.G.
        title = QLabel("A.L.I.G.")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 45px; font-weight: bold; color: #1F6AA5; margin-bottom: 10px;")
        layout.addWidget(title)

        # Zone Historique (Simplifiée pour l'instant)
        layout.addWidget(QLabel(self.texts.get("history", "History")))
        self.history_area = QScrollArea()
        self.history_area.setWidgetResizable(True)
        self.history_area.setStyleSheet("background-color: #202020; border-radius: 10px; border: 1px solid #333;")
        
        # On créera la grille de thumbnails ici
        thumb_widget = QWidget()
        self.thumb_grid = QGridLayout(thumb_widget)
        self.history_area.setWidget(thumb_widget)
        layout.addWidget(self.history_area)

        # Statistiques
        self.setup_stats(layout)

        self.main_layout.addWidget(right_container)

    def setup_stats(self, parent_layout):
        stats_frame = QFrame()
        stats_frame.setFixedHeight(100)
        stats_frame.setStyleSheet("background-color: #2b2b2b; border-radius: 15px; border: 1px solid #3d3d3d;")
        
        layout = QHBoxLayout(stats_frame)
        
        # Récupération des stats
        cfg = self.controller.config_manager
        total_l = cfg.get_item("stats", "total_lines", 0)
        
        # Item simple pour l'exemple
        for label, value in [(self.texts["lines_generated"], f"{int(total_l):,}")]:
            v_layout = QVBoxLayout()
            val_lbl = QLabel(value)
            val_lbl.setStyleSheet("color: #1F6AA5; font-size: 18px; font-weight: bold; border: none;")
            txt_lbl = QLabel(label)
            txt_lbl.setStyleSheet("color: gray; font-size: 11px; border: none;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            txt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v_layout.addWidget(val_lbl)
            v_layout.addWidget(txt_lbl)
            layout.addLayout(v_layout)

        parent_layout.addWidget(stats_frame)