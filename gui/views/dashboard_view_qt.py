# -*- coding: utf-8 -*-
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, 
                             QLabel, QScrollArea, QGridLayout, QPushButton)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QPixmap, QIcon, QFont
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor


from core.translations import TRANSLATIONS
from utils.paths import THUMBNAILS_DIR, ASSETS_DIR, SVG_ICONS
from utils.paths import SVG_ICONS
from gui.utils_qt import get_svg_pixmap

class DashboardViewQt(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        
        # Récupération des textes
        lang = self.controller.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"])["dashboard"]
        self.text = TRANSLATIONS.get(lang, TRANSLATIONS["English"]).get("topbar", {})

        # Layout Principal (Horizontal : Gauche = Modes, Droite = Histoire/Stats)
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(30, 20, 30, 20)
        self.main_layout.setSpacing(30)

        # --- COLONNE GAUCHE : MODES (Scrollable) ---
        self.setup_left_column()

        # --- COLONNE DROITE : TITRE + HISTORY + STATS ---
        self.setup_right_column()

        # --- THUMBNAILS ---
        self.load_thumbnails()
        QTimer.singleShot(100, self.render_grid)


    def setup_left_column(self):
        left_container = QFrame()
        left_container.setFixedWidth(420)
        layout = QVBoxLayout(left_container)
        layout.setContentsMargins(0, 0, 0, 10) 

        # 1. Zone de défilement
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        self.modes_layout = QVBoxLayout(content)
        self.modes_layout.setSpacing(15)
        self.modes_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- LISTE DES MODES MISE À JOUR ---
        # On utilise maintenant SVG_ICONS pour les chemins
        modes = [
            # (Titre, Description, Callback, Icône (Path ou Emoji), État)
            (self.texts["raster_title"], self.texts["raster_desc"], self.controller.show_raster_mode, SVG_ICONS["RASTER"], "normal"),
            (self.texts["dithering_title"], self.texts["dithering_desc"], None, "🏁", "disabled"),
            (self.texts["infill_title"], self.texts["infill_desc"], None, "📐", "disabled"),
            (self.texts["parser_title"], self.texts["parser_desc"], None, "📐", "disabled"),
            (self.texts["calibration_title"], self.texts["calibration_desc"], self.controller.show_calibration_mode, SVG_ICONS["LATENCY"], "normal"),
            # Utilisation de l'icône Home ou Settings (ici Home pour l'exemple)
            (self.texts["settings_title"], self.texts["settings_desc"], self.controller.show_settings_mode, "⚙️", "normal"),
        ]

        for title, desc, callback, icon_source, state in modes:
            # On passe icon_source qui peut être soit un chemin SVG, soit un Emoji
            card = self.create_mode_card(title, desc, callback, icon_source, state)
            self.modes_layout.addWidget(card)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # --- SECTION CRÉDITS ---
        credits_label = QLabel(self.text.get("credits", "By MoMo"))
        credits_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits_label.setStyleSheet("color: #444444; font-size: 12px; border: none; background: transparent;")
        layout.addWidget(credits_label)

        self.main_layout.addWidget(left_container)

        

    def create_mode_card(self, title, desc, callback, icon_data, state):
        """Crée une carte de mode avec hauteur fixe et gestion d'état (SVG/PNG/Emoji)"""
        from gui.utils_qt import get_svg_pixmap  # Import local ou en haut de fichier
        
        card = QFrame()
        card.setObjectName("modeCard")

        card.icon_data = icon_data
        card.state = state
        
        # 1. FIXER LA HAUTEUR (Uniformité visuelle)
        card.setFixedHeight(80)
        
        # Définition des états
        is_disabled = (state == "disabled" or callback is None)
        bg_color = "#1e1e1e" if is_disabled else "#2b2b2b"
        border_color = "#252525" if is_disabled else "#3d3d3d"
        title_color = "#777777" if is_disabled else "white"
        desc_color = "#555555" if is_disabled else "gray"
        # Couleur pour l'icône SVG : Gris si désactivé, Blanc si actif
        icon_color = "#555555" if is_disabled else "#FFFFFF"

        # 2. STYLE QSS (Design Moderne)
        style = f"""
            QFrame#modeCard {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 15px;
            }}
        """
        if not is_disabled:
            style += """
                QFrame#modeCard:hover {
                    border-color: #1F6AA5;
                    background-color: #333333;
                }
            """
            card.setCursor(Qt.CursorShape.PointingHandCursor)
        
        card.setStyleSheet(style)

        # 3. LAYOUT HORIZONTAL PRINCIPAL
        layout = QHBoxLayout(card)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)

        # 4. LOGIQUE D'ICÔNE MULTI-FORMAT
        icon_label = QLabel()
        icon_label.setFixedWidth(45) # Largeur fixe pour aligner les textes
        
        if isinstance(icon_data, str) and icon_data.endswith(".svg"):
            # CAS 1 : SVG dynamique
            pix = get_svg_pixmap(icon_data, size=QSize(35, 35), color_hex=icon_color)
            icon_label.setPixmap(pix)
            
        elif isinstance(icon_data, str) and icon_data.endswith(".png"):
            # CAS 2 : PNG classique
            path = os.path.join(ASSETS_DIR, icon_data)
            pix = QPixmap(path).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(pix)
            
        else:
            # CAS 3 : Emoji ou Texte
            icon_label.setText(icon_data)
            icon_label.setFont(QFont("Arial", 24))
            icon_label.setStyleSheet(f"color: {title_color}; border: none; background: transparent;")
        
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # 5. ZONE DE TEXTE (Verticale)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        # Titre
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"color: {title_color}; font-weight: bold; font-size: 15px; border: none; background: transparent;")
        
        # Description
        d_lbl = QLabel(desc)
        d_lbl.setWordWrap(True)
        d_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        d_lbl.setStyleSheet(f"color: {desc_color}; font-size: 11px; border: none; background: transparent;")
        
        text_layout.addWidget(t_lbl)
        text_layout.addWidget(d_lbl)
        text_layout.addStretch()
        
        layout.addLayout(text_layout)
        layout.setStretch(1, 1)

        card.icon_label = icon_label
        card.title_label = t_lbl
        card.desc_label = d_lbl

        # 6. GESTION DU CLIC
        if not is_disabled:
            card.mousePressEvent = lambda e: callback()
        else:
            card.mousePressEvent = lambda e: None

        return card

    def setup_right_column(self):
        right_container = QWidget()
        layout = QVBoxLayout(right_container)
        layout.setContentsMargins(0, 0, 0, 0)

        # Titre A.L.I.G.
        title = QLabel("ALIG")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(100)
        glow.setColor(QColor(31, 106, 165, 200)) # Bleu ALIG
        glow.setOffset(0)
        title.setGraphicsEffect(glow)

        title.setStyleSheet("font-size: 60px; font-weight: 900; color: #ADE1FF; letter-spacing: 10px;")
        
        layout.addWidget(title)

        # Zone Historique (Simplifiée pour l'instant)
        history_label = QLabel(self.texts.get("history", "History"))
        history_label.setStyleSheet("font-weight: bold; color: white; margin-top: 10px;")
        layout.addWidget(history_label)

        self.history_area = QScrollArea() 
        self.history_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_area.setWidgetResizable(True)
        self.history_area.setStyleSheet("background-color: #202020; border-radius: 10px; border: 1px solid #333;")
        self.history_area.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: #202020;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #3e3e3e;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #1F6AA5; /* Ton bleu ALIG au survol */
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.history_area.verticalScrollBar().setSingleStep(15)
        
        thumb_widget = QWidget()
        thumb_widget.setStyleSheet("background: transparent;") # Important pour le look
        self.thumb_grid = QGridLayout(thumb_widget)
        self.thumb_grid.setSpacing(15) # Un peu d'espace entre les vignettes
        
        self.history_area.setWidget(thumb_widget)
        layout.addWidget(self.history_area)

        # Statistiques
        self.setup_stats(layout)

        self.main_layout.addWidget(right_container)

    def load_thumbnails(self):
        thumb_dir = THUMBNAILS_DIR
        self.all_pixmaps = [] # On stocke des QPixmap au lieu de CTkImage
        
        if not os.path.exists(thumb_dir):
            os.makedirs(thumb_dir, exist_ok=True)
            self.render_grid()
            return

        try:
            # Récupération et tri des fichiers (identique à ton ancienne logique)
            files = [f for f in os.listdir(thumb_dir) if f.lower().endswith(".png")]
            files = [f for f in files if os.path.isfile(os.path.join(thumb_dir, f))]
            files.sort(key=lambda x: os.path.getmtime(os.path.join(thumb_dir, x)), reverse=True)

            for file in files:
                try:
                    path = os.path.join(thumb_dir, file)
                    if os.path.getsize(path) == 0: continue

                    # En Qt, on charge directement le chemin avec QPixmap
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        # On redimensionne tout de suite pour garder de bonnes perfs
                        pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, 
                                             Qt.TransformationMode.SmoothTransformation)
                        self.all_pixmaps.append(pixmap)
                        
                except Exception as e:
                    print(f"Erreur chargement vignette {file}: {e}")
                    
        except Exception as e:
            print(f"Erreur accès dossier thumbnails: {e}")

        self.render_grid()

    def render_grid(self):
        """Affiche les vignettes en s'assurant de ne JAMAIS déclencher le scroll horizontal"""
        # 1. Nettoyage
        while self.thumb_grid.count():
            item = self.thumb_grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        if not hasattr(self, 'all_pixmaps') or not self.all_pixmaps:
            return

        # 2. CALCUL DU NOMBRE DE COLONNES
        # On définit une largeur MINIMALE pour une vignette
        min_item_width = 200 
        
        # IMPORTANT : On retire une marge de sécurité (30px) pour la scrollbar verticale
        # et les éventuels paddings/borders de la grille.
        available_width = self.history_area.viewport().width() - 30
        
        # Sécurité si le widget n'est pas encore totalement rendu
        if available_width < 100: available_width = 400

        max_columns = max(1, available_width // min_item_width)

        # 3. CONFIGURATION DU STRETCH
        # On reset les colonnes précédentes (Qt garde les stretchs en mémoire sinon)
        for i in range(self.thumb_grid.columnCount() + 1):
            self.thumb_grid.setColumnStretch(i, 0)
            
        for i in range(max_columns):
            self.thumb_grid.setColumnStretch(i, 1)

        # 4. PLACEMENT DES VIGNETTES
        # Largeur précise d'une colonne pour le calcul des images
        col_w = available_width // max_columns

        for i, pixmap in enumerate(self.all_pixmaps):
            row = i // max_columns
            col = i % max_columns
            
            container = QFrame()
            container.setFixedHeight(220) 
            container.setStyleSheet("""
                QFrame { 
                    background-color: #2b2b2b; 
                    border-radius: 8px; 
                    border: 1px solid #3d3d3d;
                }
                QFrame:hover { border-color: #1F6AA5; background-color: #333333; }
            """)
            
            v_layout = QVBoxLayout(container)
            v_layout.setContentsMargins(5, 5, 5, 5) # Espace interne au cadre
            
            img_label = QLabel()
            # On scale l'image pour qu'elle soit un peu plus petite que le cadre
            # afin de ne pas "forcer" sur les bords du layout
            scaled_pix = pixmap.scaled(
                col_w - 20, 190, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            
            img_label.setPixmap(scaled_pix)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_label.setStyleSheet("border: none; background: transparent;")
            
            v_layout.addWidget(img_label)
            self.thumb_grid.addWidget(container, row, col)

        # 5. ALIGNEMENT ET SPACING
        self.thumb_grid.setSpacing(10) # Espace entre les vignettes
        self.thumb_grid.setAlignment(Qt.AlignmentFlag.AlignTop)


    def setup_stats(self, parent_layout):
        # 1. Création du conteneur principal
        stats_frame = QFrame()
        stats_frame.setFixedHeight(120) # Un peu plus haut pour laisser respirer les textes
        stats_frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e; 
                border-radius: 15px; 
                border: 1px solid #3d3d3d;
            }
        """)
        
        # Layout horizontal pour répartir les 3 colonnes de stats
        main_layout = QHBoxLayout(stats_frame)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 2. Récupération et calcul des données (Logique conservée)
        cfg = self.controller.config_manager
        total_l = cfg.get_item("stats", "total_lines", 0)
        total_g = cfg.get_item("stats", "total_gcodes", 0)
        total_s = float(cfg.get_item("stats", "total_time_seconds", 0))

        # Conversion du temps
        hours = int(total_s // 3600)
        minutes = int((total_s % 3600) // 60)
        
        if hours > 0:
            time_str = f"{hours}h {minutes:02d}m"
        elif minutes > 0:
            time_str = f"{minutes}m"
        elif total_s > 0:
            time_str = "< 1m"
        else:
            time_str = "0m"

        # 3. Définition des items à afficher
        stat_items = [
            (f"{int(total_l):,}", self.texts.get("lines_generated", "Lines")),
            (str(total_g), self.texts.get("gcode_saved", "G-Codes")),
            (time_str, self.texts.get("total_engraving_time", "Time"))
        ]

        # 4. Création dynamique des colonnes
        for value, label in stat_items:
            v_layout = QVBoxLayout()
            v_layout.setSpacing(2) # Espace réduit entre valeur et texte
            
            # Valeur (Bleu et gras)
            val_lbl = QLabel(value)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl.setStyleSheet("color: #1F6AA5; font-size: 18px; font-weight: bold; border: none; background: transparent;")
            
            # Label (Petit et gris)
            txt_lbl = QLabel(label)
            txt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            txt_lbl.setWordWrap(True) # Au cas où le texte est long
            txt_lbl.setStyleSheet("color: gray; font-size: 10px; border: none; background: transparent;")
            
            v_layout.addWidget(val_lbl)
            v_layout.addWidget(txt_lbl)
            
            # On ajoute chaque colonne au layout horizontal
            main_layout.addLayout(v_layout)
            
            # Ajouter un séparateur vertical entre les colonnes (sauf après la dernière)
            if label != stat_items[-1][1]:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.VLine)
                line.setStyleSheet("color: #3d3d3d; background-color: #3d3d3d; width: 1px; margin: 15px 0;")
                main_layout.addWidget(line)

        # Ajout du bloc complet au layout de la colonne de droite
        parent_layout.addWidget(stats_frame)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # On ne rafraîchit la grille que si la vue est prête
        if hasattr(self, 'history_area'):
            self.render_grid()

    def apply_theme(self, colors):
        """Met à jour toutes les cartes du dashboard lors d'un changement de thème"""
        from gui.utils_qt import get_svg_pixmap
        from PyQt6.QtCore import QSize

        # 1. Mettre à jour le fond de la vue elle-même
        # On utilise une version légèrement plus sombre ou claire pour le contraste
        self.setStyleSheet(f"background-color: transparent;")

        # 2. Parcourir toutes les cartes de mode
        # Supposons que vos cartes sont dans self.modes_layout
        for i in range(self.modes_layout.count()):
            item = self.modes_layout.itemAt(i)
            if not item: continue
            card = item.widget()
            if not card or card.objectName() != "modeCard": continue

            is_disabled = (card.state == "disabled")
            
            # Définition des couleurs selon le thème reçu
            if is_disabled:
                bg = "#1e1e1e" if colors["suffix"] == "_DARK" else "#E0E0E0"
                txt = "#777777"
                icon_c = "#555555"
            else:
                bg = colors["bg_card"]
                txt = colors["text"]
                icon_c = colors["text"]

            # Mise à jour du style de la carte
            card.setStyleSheet(f"""
                QFrame#modeCard {{
                    background-color: {bg};
                    border: 2px solid {colors['border']};
                    border-radius: 15px;
                }}
            """)

            # Mise à jour des labels
            card.title_label.setStyleSheet(f"color: {txt}; font-weight: bold; font-size: 15px; border: none; background: transparent;")
            card.desc_label.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 11px; border: none; background: transparent;")

            # Mise à jour de l'icône SVG si nécessaire
            if isinstance(card.icon_data, str) and card.icon_data.endswith(".svg"):
                pix = get_svg_pixmap(card.icon_data, size=QSize(35, 35), color_hex=icon_c)
                card.icon_label.setPixmap(pix)