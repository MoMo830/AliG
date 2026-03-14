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
from gui.utils_qt import get_svg_pixmap

class DashboardViewQt(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setStyleSheet("background-color: #2b2b2b; color: white;")

        self.translation_map = {}
        
        # Récupération des textes
        lang = self.controller.config_manager.get_item("machine_settings", "language", "English")
        self.texts = TRANSLATIONS.get(lang, TRANSLATIONS["English"])["dashboard"]
        self.text = TRANSLATIONS.get(lang, TRANSLATIONS["English"]).get("topbar", {})

        # 1. Layout Global VERTICAL
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 20, 30, 20)
        self.main_layout.setSpacing(5)

        # 2. LOGO en haut (Pleine largeur)
        self.setup_logo_header()

        # --- ligne de séparation ---
        line = QFrame()
        line.setFixedHeight(5) 
        line.setStyleSheet(f"""
            background-color: #444; 
            margin-left: 50px; 
            margin-right: 50px;
        """)

        self.main_layout.addWidget(line)

        # 3. Conteneur HORIZONTAL pour le reste
        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(30)
        self.main_layout.addLayout(self.content_layout)

        # 4. Appels des fonctions de création
        self.setup_left_column()   # Ira dans content_layout (à gauche)
        self.setup_right_column()  # Ira dans content_layout (à droite)

        # --- THUMBNAILS ---
        self.load_thumbnails()
        QTimer.singleShot(0, self.render_grid)

    def setup_logo_header(self):
        """Crée le bandeau titre ALIG en haut de la vue"""
        self.logo_label = QLabel("ALIG")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Effet de lueur (Glow)
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(40)
        glow.setColor(QColor(31, 106, 165, 200)) 
        glow.setOffset(0)
        self.logo_label.setGraphicsEffect(glow)

        # Style agrandi pour le mode plein écran
        self.logo_label.setStyleSheet("""
            font-size: 70px; 
            font-weight: 900; 
            color: #ADE1FF; 
            letter-spacing: 15px; 
            margin-bottom: 10px;
            background: transparent;
        """)
        
        # On l'ajoute au layout VERTICAL principal
        self.main_layout.addWidget(self.logo_label)

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
            ("raster_title",      "raster_desc",      self.controller.show_raster_mode,     SVG_ICONS["RASTER"],  "normal"),
            ("dithering_title",   "dithering_desc",   None,                                  SVG_ICONS["DITHER"],  "disabled"),
            ("infill_title",      "infill_desc",       None,                                  SVG_ICONS["INFILL"],  "disabled"),
            ("parser_title",      "parser_desc",       self.controller.show_checker_mode,    SVG_ICONS["GCODE"],   "normal"),
            ("calibration_title", "calibration_desc",  self.controller.show_calibration_mode,SVG_ICONS["LATENCY"], "normal"),
            ("settings_title",    "settings_desc",     self.controller.show_settings_mode,   SVG_ICONS["GEAR"],    "normal"),
        ]

        for title_key, desc_key, callback, icon_source, state in modes:
            card = self.create_mode_card(title_key, desc_key, callback, icon_source, state)
            self.modes_layout.addWidget(card)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # --- SECTION CRÉDITS ---
        credits_label = QLabel(self.text.get("credits", "By MoMo"))
        credits_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits_label.setStyleSheet("color: #444444; font-size: 12px; border: none; background: transparent;")
        layout.addWidget(credits_label)

        self.content_layout.addWidget(left_container)

        

    def create_mode_card(self, title_key, desc_key, callback, icon_data, state):
        """Crée une carte de mode et enregistre ses labels pour la traduction"""
        from gui.utils_qt import get_svg_pixmap
        
        card = QFrame()
        card.setAttribute(Qt.WidgetAttribute.WA_Hover)
        card.setObjectName("modeCard")
        card.icon_data = icon_data
        card.state = state
        card.setFixedHeight(80)
        
        is_disabled = (state == "disabled" or callback is None)
        bg_color = "#1e1e1e" if is_disabled else "#2b2b2b"
        border_color = "#252525" if is_disabled else "#3d3d3d"
        title_color = "#777777" if is_disabled else "white"
        desc_color = "#555555" if is_disabled else "gray"
        icon_color = "#555555" if is_disabled else "#FFFFFF"

        style = f"""
            QFrame#modeCard {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 15px;
            }}
        """
        if not is_disabled:
            style += "QFrame#modeCard:hover { border-color: #1F6AA5; background-color: #333333; }"
            card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(style)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)

        # Icône
        icon_label = QLabel()
        icon_label.setFixedWidth(45)
        if isinstance(icon_data, str) and icon_data.endswith(".svg"):
            pix = get_svg_pixmap(icon_data, size=QSize(35, 35), color_hex=icon_color)
            icon_label.setPixmap(pix)
        elif isinstance(icon_data, str) and icon_data.endswith(".png"):
            path = os.path.join(ASSETS_DIR, icon_data)
            pix = QPixmap(path).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(pix)
        else:
            icon_label.setText(icon_data)
            icon_label.setFont(QFont("Arial", 24))
            icon_label.setStyleSheet(f"color: {title_color}; border: none; background: transparent;")
        
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Zone de texte
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        # --- TITRE (Enregistré dans la map) ---
        t_lbl = QLabel(self.texts.get(title_key, title_key))
        t_lbl.setStyleSheet(f"color: {title_color}; font-weight: bold; font-size: 15px; border: none; background: transparent;")
        self.translation_map[t_lbl] = title_key # Stockage de la clé
        
        # --- DESCRIPTION (Enregistrée dans la map) ---
        d_lbl = QLabel(self.texts.get(desc_key, desc_key))
        d_lbl.setWordWrap(True)
        d_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        d_lbl.setStyleSheet(f"color: {desc_color}; font-size: 11px; border: none; background: transparent;")
        self.translation_map[d_lbl] = desc_key # Stockage de la clé
        
        text_layout.addWidget(t_lbl)
        text_layout.addWidget(d_lbl)
        text_layout.addStretch()
        
        layout.addLayout(text_layout)
        layout.setStretch(1, 1)

        card.icon_label = icon_label
        card.title_label = t_lbl
        card.desc_label = d_lbl

        if not is_disabled:
            card.mousePressEvent = lambda e: callback()
        else:
            card.mousePressEvent = lambda e: None

        for child in card.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        return card
    


    def setup_right_column(self):
        right_container = QWidget()
        layout = QVBoxLayout(right_container)
        layout.setContentsMargins(0, 0, 0, 0)

        # # Titre A.L.I.G.
        # title = QLabel("ALIG")
        # title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # glow = QGraphicsDropShadowEffect()
        # glow.setBlurRadius(100)
        # glow.setColor(QColor(31, 106, 165, 200)) # Bleu ALIG
        # glow.setOffset(0)
        # title.setGraphicsEffect(glow)

        # title.setStyleSheet("font-size: 60px; font-weight: 900; color: #ADE1FF; letter-spacing: 10px;")
        
        # layout.addWidget(title)

        # Zone Historique (Simplifiée pour l'instant)
        self.history_label = QLabel(self.texts.get("history", "History"))
        self.history_label.setStyleSheet("font-weight: bold; color: white; margin-top: 10px; background: transparent; border: none;")
        layout.addWidget(self.history_label)

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

        self.content_layout.addWidget(right_container)

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
            # Utilise les couleurs du thème courant si disponibles
            _c = getattr(self, "_current_colors", None)
            if _c:
                bg   = _c["bg_card"]
                brd  = _c["border"]
            else:
                bg   = "#2b2b2b"
                brd  = "#3d3d3d"
            container.setStyleSheet(f"""
                QFrame {{ 
                    background-color: {bg}; 
                    border-radius: 8px; 
                    border: 1px solid {brd};
                }}
                QFrame:hover {{ border-color: #1F6AA5; background-color: {bg}; }}
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
        self.stats_frame = QFrame()
        self.stats_frame.setFixedHeight(120)
        self.stats_frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e; 
                border-radius: 15px; 
                border: 1px solid #3d3d3d;
            }
        """)
        
        main_layout = QHBoxLayout(self.stats_frame)
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
        self._stat_value_labels = []
        self._stat_key_labels   = []
        for value, label in stat_items:
            v_layout = QVBoxLayout()
            v_layout.setSpacing(2) # Espace réduit entre valeur et texte
            
            # Valeur (Bleu et gras)
            val_lbl = QLabel(value)
            self._stat_value_labels.append(val_lbl)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl.setStyleSheet("color: #1F6AA5; font-size: 18px; font-weight: bold; border: none; background: transparent;")
            
            # Label (Petit et gris)
            txt_lbl = QLabel(label)
            self._stat_key_labels.append(txt_lbl)
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
        parent_layout.addWidget(self.stats_frame)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # On ne rafraîchit la grille que si la vue est prête
        if hasattr(self, 'history_area'):
            self.render_grid()

    def apply_theme(self, colors):
        """Met à jour toutes les cartes du dashboard lors d'un changement de thème"""
        from gui.utils_qt import get_svg_pixmap
        from PyQt6.QtCore import QSize

        self._current_colors = colors

        # 1. Fond de la vue
        self.setStyleSheet("background-color: transparent;")

        # 2. Label "History"
        if hasattr(self, "history_label"):
            self.history_label.setStyleSheet(
                f"font-weight: bold; color: {colors['text']}; "
                "margin-top: 10px; background: transparent; border: none;"
            )

        # 3. Cadre thumbnails (history_area)
        if hasattr(self, "history_area"):
            self.history_area.setStyleSheet(
                f"background-color: {colors['bg_card']}; "
                "border-radius: 10px; border: 1px solid "
                f"{colors['border']};"
            )
            self.history_area.verticalScrollBar().setStyleSheet(f"""
                QScrollBar:vertical {{
                    border: none;
                    background: {colors['scrollbar_bg']};
                    width: 10px;
                    margin: 0px;
                }}
                QScrollBar::handle:vertical {{
                    background: {colors['scrollbar_handle']};
                    min-height: 20px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: #1F6AA5;
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: none;
                }}
            """)

        # 4. Frame de statistiques
        if hasattr(self, "stats_frame"):
            self.stats_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {colors['bg_card']};
                    border-radius: 15px;
                    border: 1px solid {colors['border']};
                }}
            """)

        # 5. Cartes de mode
        hover_bg = colors['hover_card']
        for i in range(self.modes_layout.count()):
            item = self.modes_layout.itemAt(i)
            if not item: continue
            card = item.widget()
            if not card or card.objectName() != "modeCard": continue

            is_disabled = (card.state == "disabled")

            if is_disabled:
                bg     = colors['bg_main']
                txt    = colors['text_disabled']
                icon_c = colors['text_disabled']
            else:
                bg     = colors["bg_card"]
                txt    = colors["text"]
                icon_c = colors["text"]

            if is_disabled:
                card.setStyleSheet(f"""
                    QFrame#modeCard {{
                        background-color: {bg};
                        border: 2px solid {colors['border']};
                        border-radius: 15px;
                    }}
                """)
            else:
                card.setStyleSheet(f"""
                    QFrame#modeCard {{
                        background-color: {bg};
                        border: 2px solid {colors['border']};
                        border-radius: 15px;
                    }}
                    QFrame#modeCard:hover {{
                        border-color: #1F6AA5;
                        background-color: {hover_bg};
                    }}
                """)

            card.title_label.setStyleSheet(
                f"color: {txt}; font-weight: bold; font-size: 15px; "
                "border: none; background: transparent;"
            )
            card.desc_label.setStyleSheet(
                f"color: {colors['text_secondary']}; font-size: 11px; "
                "border: none; background: transparent;"
            )

            if isinstance(card.icon_data, str) and card.icon_data.endswith(".svg"):
                pix = get_svg_pixmap(card.icon_data, size=QSize(35, 35), color_hex=icon_c)
                card.icon_label.setPixmap(pix)

        # 6. Re-rendu des vignettes avec les nouvelles couleurs
        if hasattr(self, "all_pixmaps"):
            self.render_grid()

    def _apply_language(self, lang: str, translations: dict):
        """Reçoit lang directement — utilisé par update_ui_language."""
        from core.translations import TRANSLATIONS as _TR
        self.texts = _TR.get(lang, _TR["English"])["dashboard"]
        from gui.utils_qt import translate_ui_widgets
        translate_ui_widgets(self.translation_map, self.texts)
        if hasattr(self, 'history_label'):
            self.history_label.setText(self.texts.get("history", "History"))
        stat_keys = ["lines_generated", "gcode_saved", "total_engraving_time"]
        for i, key in enumerate(stat_keys):
            labels = getattr(self, '_stat_key_labels', [])
            if i < len(labels):
                labels[i].setText(self.texts.get(key, key))

    def update_texts(self):
        """Met à jour dynamiquement tous les labels du Dashboard"""
        lang = self.controller.config_manager.get_item("machine_settings", "language", "English")
        self._apply_language(lang, {})

    def refresh(self):
        """Recharge les stats et les vignettes depuis le disque."""
        # Mettre à jour les stats si les labels existent déjà
        if hasattr(self, '_stat_value_labels') and len(self._stat_value_labels) == 3:
            cfg = self.controller.config_manager
            total_l = cfg.get_item("stats", "total_lines", 0)
            total_g = cfg.get_item("stats", "total_gcodes", 0)
            total_s = float(cfg.get_item("stats", "total_time_seconds", 0))

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

            self._stat_value_labels[0].setText(f"{int(total_l):,}")
            self._stat_value_labels[1].setText(str(total_g))
            self._stat_value_labels[2].setText(time_str)

        # Recharger les vignettes
        self.load_thumbnails()