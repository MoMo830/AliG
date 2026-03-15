# -*- coding: utf-8 -*-
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame,
                             QLabel, QScrollArea, QGridLayout, QPushButton,
                             QStackedWidget)
from PyQt6.QtCore import Qt, QSize, QTimer, QPoint
from PyQt6.QtGui import QPixmap, QIcon, QFont
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor


from core.translations import TRANSLATIONS
from utils.paths import THUMBNAILS_DIR, ASSETS_DIR, SVG_ICONS
from gui.utils_qt import get_svg_pixmap
from gui.onboarding_widget import OnboardingWidget, HighlightOverlay

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
        QTimer.singleShot(0, self._init_history_area)

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
        left_container.setStyleSheet("background: transparent;")
        self._left_container = left_container
        layout = QVBoxLayout(left_container)
        layout.setContentsMargins(0, 0, 0, 10) 

        # 1. Zone de défilement
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll.viewport().setStyleSheet("background: transparent;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
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
        right_container.setStyleSheet("background: transparent;")
        self._right_container = right_container
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
        self.history_area.setStyleSheet("background: transparent; border-radius: 10px; border: 1px solid #333;")
        self.history_area.viewport().setStyleSheet("background: transparent;")
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
        
        # Conteneur stacké : page 0 = onboarding, page 1 = grille vignettes
        self._history_stack_widget = QWidget()
        self._history_stack_widget.setStyleSheet("background: transparent;")
        stack_outer = QVBoxLayout(self._history_stack_widget)
        stack_outer.setContentsMargins(0, 0, 0, 0)
        stack_outer.setSpacing(0)

        self._history_stack = QStackedWidget()
        self._history_stack.setStyleSheet("background: transparent;")

        # Page 0 — onboarding (créé dans _init_history_area)
        self._onboarding_placeholder = QWidget()
        self._onboarding_placeholder.setStyleSheet("background: transparent;")
        self._history_stack.addWidget(self._onboarding_placeholder)

        # Page 1 — grille de vignettes
        thumb_widget = QWidget()
        thumb_widget.setStyleSheet("background: transparent;")
        self.thumb_grid = QGridLayout(thumb_widget)
        self.thumb_grid.setSpacing(15)
        self._history_stack.addWidget(thumb_widget)

        stack_outer.addWidget(self._history_stack)
        self.history_area.setWidget(self._history_stack_widget)
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
        # S'assurer qu'on est bien sur la page vignettes
        if hasattr(self, "_history_stack") and self._history_stack.currentIndex() != 1:
            return

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


    def _init_history_area(self):
        """Décide si on affiche l'onboarding ou directement les vignettes."""
        cfg = self.controller.config_manager
        first_launch = cfg.get_item("app_state", "onboarding_done", False)

        if not first_launch:
            lang = self.controller.config_manager.get_item("machine_settings", "language", "English")
            self._build_onboarding(lang, is_initial=True)
            # Overlay placé sur la fenêtre principale
            self._hl_overlay = HighlightOverlay(self.window())
            self._hl_overlay.resize(self.window().size())
            self._hl_overlay.hide()
            self._history_stack.setCurrentIndex(0)
        else:
            self._history_stack.setCurrentIndex(1)
            self.render_grid()

    def restart_onboarding(self):
        """Relance l'onboarding depuis zéro — appelé depuis settings reset.
        Recrée l'overlay, remet les cartes en état désactivé, lance le watcher.
        """
        lang = self.controller.config_manager.get_item(
            "machine_settings", "language", "English")
        # S'assurer que l'overlay est bien positionné sur la fenêtre principale
        main_win = self.window()
        if not hasattr(self, '_hl_overlay'):
            from gui.onboarding_widget import HighlightOverlay
            self._hl_overlay = HighlightOverlay(main_win)
        self._hl_overlay.setParent(main_win)
        self._hl_overlay.resize(main_win.size())
        self._hl_overlay.move(0, 0)
        self._hl_overlay.hide()
        self._last_highlight_names = []
        # Restaurer le style des cartes avant de les redésactiver
        self._set_mode_cards_enabled(True)
        # Reconstruire et afficher l'onboarding
        self._build_onboarding(lang, is_initial=True)
        self._history_stack.setCurrentIndex(0)
        self._apply_history_area_style()

    def _build_onboarding(self, lang, step=0, is_initial=False):
        """Crée (ou recrée) l'OnboardingWidget pour la langue donnée.
        Remplace le widget courant dans _history_stack[0].
        step        : étape à restaurer après reconstruction.
        is_initial  : True = premier lancement, active le watcher géométrie."""
        from core.translations import TRANSLATIONS
        colors = getattr(self, "_current_colors", None) or {
            "text": "#dddddd", "text_secondary": "#aaaaaa",
            "bg_card_alt": "#2a2a2a", "bg_entry": "#2b2b2b",
            "border_strong": "#555", "border": "#333",
            "bg_card": "#2b2b2b",
        }
        onb_t = TRANSLATIONS.get(lang, TRANSLATIONS["English"]).get("onboarding", {})
        new_onb = OnboardingWidget(
            colors, translations=onb_t,
            current_lang=lang,
            emit_initial_highlight=False,  # on gère le highlight manuellement
            parent=self
        )
        new_onb.finished.connect(self._on_onboarding_finished)
        new_onb.request_highlight.connect(self._on_request_highlight)
        new_onb.clear_highlight.connect(self._on_clear_highlight)
        new_onb.language_changed.connect(self._on_onboarding_lang_changed)
        # Restaurer l'étape courante
        if step > 0:
            new_onb._step = step
            new_onb._stack.setCurrentIndex(step)
            new_onb._refresh(emit_highlight=False)
        # Remplacer dans le stack et s'assurer qu'il est visible
        old_w = self._history_stack.widget(0)
        self._history_stack.removeWidget(old_w)
        old_w.deleteLater()
        self._history_stack.insertWidget(0, new_onb)
        self._history_stack.setCurrentIndex(0)
        self._onboarding = new_onb
        # Désactiver les cartes pendant l'onboarding
        self._set_mode_cards_enabled(False)
        if is_initial:
            # Premier lancement : attendre que la géométrie soit stable
            # (fenêtre potentiellement maximisée)
            new_onb._emit_initial_highlight = True
            new_onb._geom_attempts = 0
            new_onb._last_win_size = None
            from PyQt6.QtCore import QTimer
            new_onb._geom_timer = QTimer(new_onb)
            new_onb._geom_timer.timeout.connect(new_onb._wait_geometry_stable)
            new_onb._geom_timer.start(60)
        else:
            # Rebuild (changement de langue) : highlight immédiat sans flash
            new_onb._emit_highlight()

    def _set_mode_cards_enabled(self, enabled: bool):
        """Active ou désactive les cartes via CSS uniquement.
        QGraphicsOpacityEffect est évité car il propage son rendu
        aux widgets frères (dont l'onboarding)."""
        for i in range(self.modes_layout.count()):
            item = self.modes_layout.itemAt(i)
            if not item:
                continue
            card = item.widget()
            if not card:
                continue
            card.setEnabled(enabled)
            if enabled:
                # Restaurer le style normal
                c = getattr(self, '_current_colors', {})
                is_dis = getattr(card, 'state', '') == 'disabled'
                bg  = c.get('bg_main', '#1e1e1e') if is_dis else c.get('bg_card', '#2b2b2b')
                brd = c.get('border', '#3d3d3d')
                hov = c.get('hover_card', '#333333')
                base = (
                    f'QFrame#modeCard {{ background-color: {bg};'
                    f' border: 2px solid {brd}; border-radius: 15px; }}'
                )
                if not is_dis:
                    base += (
                        f' QFrame#modeCard:hover {{ border-color: #1F6AA5;'
                        f' background-color: {hov}; }}'
                    )
                card.setStyleSheet(base)
                # apply_theme restaurera les styles complets au prochain cycle
            else:
                # Griser via CSS — fond sombre, textes très discrets
                card.setStyleSheet(
                    'QFrame#modeCard { background-color: #1c1c1c;'
                    ' border: 2px solid #252525; border-radius: 15px; }'
                )
                # NE PAS toucher aux labels — setEnabled(False) suffit
                # pour bloquer les clics sans affecter le rendu visuel
                pass

    def _apply_history_area_style(self, colors=None):
        """Applique le style de history_area selon l'etat de l'onboarding."""
        if colors is None:
            colors = getattr(self, '_current_colors', {})
        onboarding_active = (
            hasattr(self, '_history_stack')
            and self._history_stack.currentIndex() == 0
        )
        if onboarding_active:
            brd = colors.get('border', '#333333') if colors else '#333333'
            self.history_area.setStyleSheet(
                f"background: transparent; border-radius: 10px;"
                f" border: 1px solid {brd};"
            )
            self.history_area.viewport().setStyleSheet("background: transparent;")
        else:
            bg  = colors.get('bg_card', '#2b2b2b')
            brd = colors.get('border', '#333333')
            self.history_area.setStyleSheet(
                f"background-color: {bg};"
                " border-radius: 10px;"
                f" border: 1px solid {brd};"
            )
            self.history_area.viewport().setStyleSheet("")

    def _on_request_highlight(self, names: list):
        self._last_highlight_names = names   # mémorisé pour recalcul au resize
        """
        Reçoit la liste des noms de widgets à mettre en exergue.
        Localise chaque widget dans la fenêtre principale et
        construit les cibles pour HighlightOverlay.
        """
        if not hasattr(self, '_hl_overlay'):
            return
        main_win = self.window()
        self._hl_overlay.setParent(main_win)
        self._hl_overlay.resize(main_win.size())  # recalcul si fenêtre maximisée
        self._hl_overlay.move(0, 0)

        # Point d'ancrage = centre de la history_area converti en coords main_win
        anchor_local = QPoint(
            self.history_area.width() // 2,
            self.history_area.height() // 2,
        )
        anchor = self.history_area.mapTo(main_win, anchor_local)

        targets = []
        onboarding_already_added = False

        for name in names:
            if name == 'onboarding_area':
                # Utiliser le widget onboarding lui-même pour le rect exact
                onb_widget = getattr(self, '_onboarding', None)
                if onb_widget and onb_widget.isVisible():
                    tl_onb = onb_widget.mapTo(main_win, onb_widget.rect().topLeft())
                    rect_onb = onb_widget.rect().translated(tl_onb)
                else:
                    # Fallback : viewport de history_area
                    vp = self.history_area.viewport()
                    tl_onb = vp.mapTo(main_win, vp.rect().topLeft())
                    rect_onb = vp.rect().translated(tl_onb)
                targets.insert(0, {'rect': rect_onb, 'no_border': True})
                onboarding_already_added = True
                continue

            if name == 'modes_column':
                # Rect englobant les 3 premières cartes (Raster, Calibration, Checker)
                rects = []
                for i in range(self.modes_layout.count()):
                    if len(rects) >= 3:
                        break
                    item = self.modes_layout.itemAt(i)
                    if not item: continue
                    card = item.widget()
                    if card and card.objectName() == 'modeCard':
                        tl = card.mapTo(main_win, card.rect().topLeft())
                        rects.append(card.rect().translated(tl))
                if rects:
                    from PyQt6.QtCore import QRect
                    united = rects[0]
                    for r in rects[1:]:
                        united = united.united(r)
                    targets.append({'rect': united})
                continue

            widget = self._find_highlight_widget(name)
            if widget is None:
                continue
            tl = widget.mapTo(main_win, widget.rect().topLeft())
            rect = widget.rect().translated(tl)
            extra = {}
            # Boutons topbar : padding réduit pour éviter le débordement hors fenêtre
            if name in ('settings_topbar_btn', 'home_btn', 'github_btn'):
                extra['small_padding'] = True
            targets.append({'rect': rect, **extra})

        if targets:
            self._hl_overlay.show_highlights(targets)

    def _find_highlight_widget(self, name: str):
        """Cherche le widget correspondant au nom dans toute l'application."""
        main_win = self.window()

        if name == 'onboarding_area':
            return self.history_area

        elif name == 'all_mode_cards':
            # Retourne None ici — traité séparément dans _on_request_highlight
            return None

        elif name == 'parser_card':
            for i in range(self.modes_layout.count()):
                item = self.modes_layout.itemAt(i)
                if not item: continue
                card = item.widget()
                if card and hasattr(card, 'icon_data'):
                    from utils.paths import SVG_ICONS
                    if card.icon_data == SVG_ICONS.get('GCODE', ''):
                        return card

        elif name == 'calibration_card':
            for i in range(self.modes_layout.count()):
                item = self.modes_layout.itemAt(i)
                if not item: continue
                card = item.widget()
                if card and hasattr(card, 'icon_data'):
                    from utils.paths import SVG_ICONS
                    if card.icon_data == SVG_ICONS.get('LATENCY', ''):
                        return card

        elif name == 'settings_card':
            for i in range(self.modes_layout.count()):
                item = self.modes_layout.itemAt(i)
                if not item: continue
                card = item.widget()
                if card and hasattr(card, 'icon_data'):
                    from utils.paths import SVG_ICONS
                    if card.icon_data == SVG_ICONS.get('GEAR', ''):
                        return card

        elif name in ('settings_topbar_btn', 'home_btn', 'github_btn'):
            return self._find_topbar_btn(name, main_win)

        return None

    # Mots-clés par bouton : objectName, toolTip, text (insensible à la casse)
    _TOPBAR_KEYWORDS = {
        'settings_topbar_btn': ('setting', 'gear', 'reglage', 'einstellung'),
        'home_btn':            ('home', 'dashboard', 'accueil', 'startseite'),
        'github_btn':          ('github', 'git'),
    }

    def _find_topbar_btn(self, name, main_win):
        """Recherche un bouton topbar par objectName en priorité, puis mots-clés."""
        from PyQt6.QtWidgets import QPushButton

        # 1. Recherche directe par objectName (le plus fiable)
        btn = main_win.findChild(QPushButton, name)
        if btn:
            return btn

        # 2. Fallback : mots-clés dans objectName/toolTip/text
        #    limité aux boutons dans la topbar (Y < 80px)
        keywords = self._TOPBAR_KEYWORDS.get(name, ())
        topbar_max_y = 80
        for btn in main_win.findChildren(QPushButton):
            pos_in_win = btn.mapTo(main_win, btn.rect().topLeft())
            if pos_in_win.y() > topbar_max_y:
                continue
            all_text = ' '.join([
                btn.objectName().lower(),
                btn.toolTip().lower(),
                btn.text().lower(),
            ])
            if any(kw in all_text for kw in keywords):
                return btn

        return None
        # home = plus à gauche, settings = tout à droite (dernier)
        # github = entre les deux
        if name == 'home_btn':
            return silent[0]    # premier depuis la gauche
        elif name == 'settings_topbar_btn':
            return silent[-1]   # tout à droite
        elif name == 'github_btn':
            return silent[-2] if len(silent) >= 2 else silent[-1]
        return None

    def _highlight_label(self, name: str) -> str:
        labels = {
            'calibration_card':    'Calibration',
            'settings_card':       'Settings',
            'settings_topbar_btn': 'Settings',
        }
        return labels.get(name, '')

    def _on_onboarding_lang_changed(self, lang: str):
        """Appelé quand l'utilisateur change de langue depuis l'onboarding.
        Sauvegarde, reconstruit l'onboarding traduit et notifie la main window."""
        # 1. Sauvegarder la langue
        cfg = self.controller.config_manager
        machine = cfg.get_section("machine_settings") or {}
        machine["language"] = lang
        cfg.set_section("machine_settings", machine)
        cfg.save()
        # 2. Mémoriser l'étape courante avant reconstruction
        current_step = getattr(self._onboarding, '_step', 0)
        # 3. Reconstruire l'onboarding avec la nouvelle langue
        self._on_clear_highlight()
        self._build_onboarding(lang, step=current_step)
        # 4. Notifier la fenêtre principale
        main_win = self.window()
        if main_win and hasattr(main_win, "update_ui_language"):
            main_win.update_ui_language()

    def _on_clear_highlight(self):
        if hasattr(self, '_hl_overlay'):
            self._hl_overlay.hide_highlights()
        # Effacer les dernières cibles pour que resizeEvent
        # ne puisse pas relancer le highlight après la fin
        self._last_highlight_names = []

    def _on_onboarding_finished(self, settings: dict):
        """Appelé quand l'utilisateur termine ou skippe l'onboarding."""
        # Masquer l'overlay immédiatement, avant toute autre opération
        self._on_clear_highlight()

        cfg = self.controller.config_manager

        # Marquer comme fait
        current = cfg.get_section("app_state") or {}
        current["onboarding_done"] = True
        cfg.set_section("app_state", current)

        # Sauvegarder les réglages machine si fournis
        if settings:
            machine = cfg.get_section("machine_settings") or {}
            machine.update(settings)
            cfg.set_section("machine_settings", machine)

        cfg.save()

        # Réactiver les cartes et passer à la grille
        self._set_mode_cards_enabled(True)
        self._history_stack.setCurrentIndex(1)
        self._apply_history_area_style()
        self.render_grid()

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
        # Recalculer l'overlay si actif et qu'il reste des cibles
        if (hasattr(self, '_hl_overlay') and self._hl_overlay.isVisible()
                and getattr(self, '_last_highlight_names', [])):
            self._on_request_highlight(self._last_highlight_names)

    def apply_theme(self, colors):
        """Met à jour toutes les cartes du dashboard lors d'un changement de thème"""
        from gui.utils_qt import get_svg_pixmap
        from PyQt6.QtCore import QSize

        self._current_colors = colors

        # 1. Fond de la vue et containers
        self.setStyleSheet("background-color: transparent;")
        if hasattr(self, "_left_container"):
            self._left_container.setStyleSheet("background: transparent;")
        if hasattr(self, "_right_container"):
            self._right_container.setStyleSheet("background: transparent;")

        # 2. Label "History"
        if hasattr(self, "history_label"):
            self.history_label.setStyleSheet(
                f"font-weight: bold; color: {colors['text']}; "
                "margin-top: 10px; background: transparent; border: none;"
            )

        # 3. Cadre thumbnails (history_area)
        if hasattr(self, "history_area"):
            self._apply_history_area_style(colors)
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

        # 6. Onboarding theme
        if hasattr(self, "_onboarding"):
            self._onboarding.apply_theme(colors)

        # 7. Re-rendu des vignettes avec les nouvelles couleurs
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