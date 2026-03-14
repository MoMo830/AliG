# -*- coding: utf-8 -*-
"""
A.L.I.G. — Définition centralisée des thèmes couleur.

Usage :
    from core.themes import get_theme
    colors = get_theme("Dark")   # ou "Light"
    bg = colors["bg_main"]

Toutes les vues reçoivent ce dict via apply_theme(colors).
Plus aucune valeur hexadécimale ne doit être hardcodée dans les vues.
"""

THEMES: dict[str, dict] = {

    # ══════════════════════════════════════════════════════════════════
    #  DARK  (défaut)
    # ══════════════════════════════════════════════════════════════════
    "Dark": {
        # ── Identificateur ────────────────────────────────────────────
        "suffix":               "_DARK",

        # ── Texte ─────────────────────────────────────────────────────
        "text":                 "#DCE4EE",
        "text_secondary":       "#888888",
        "text_disabled":        "#555555",
        "text_code":            "#00ff00",      # G-Code viewer
        "text_code_dark":       "#006600",      # non utilisé en dark

        # ── Fonds principaux ──────────────────────────────────────────
        "bg_app":               "#1a1a1a",      # fenêtre racine / topbar
        "bg_main":              "#1e1e1e",      # panneaux principaux
        "bg_card":              "#252525",      # cartes / frames secondaires
        "bg_card_alt":          "#2b2b2b",      # cards calibration / settings
        "bg_deep":              "#111111",      # canvas right panel
        "bg_entry":             "#1a1a1a",      # inputs / QLineEdit / QPlainTextEdit
        "bg_entry_alt":         "#3d3d3d",      # inputs dans calibration
        "bg_canvas":            "#050505",      # canvas simulation
        "bg_scroll":            "#202020",      # fond scrollbar / sidebar calib
        "bg_speed":             "#222222",      # barre de vitesse
        "bg_speed_btn":         "#3a3a3a",      # boutons vitesse
        "bg_stats":             "#202020",      # stats raster
        "bg_tabs":              "#252525",      # fond onglets raster
        "bg_tab":               "#2b2b2b",      # onglet individuel
        "bg_preview":           "#222222",      # zone preview raster
        "bg_select":            "#1a1a1a",      # SelectContainer calibration
        "bg_opts":              "#222222",      # options panel simulation

        # ── Bordures ──────────────────────────────────────────────────
        "border":               "#333333",      # bordure standard
        "border_strong":        "#444444",      # bordure forte / inputs
        "border_light":         "#555555",      # bordure légère inputs calib
        "border_card":          "#3d3d3d",      # cartes calibration

        # ── Boutons neutres ───────────────────────────────────────────
        "btn_neutral":          "#444444",
        "btn_neutral_hover":    "#555555",
        "btn_cancel":           "#333333",
        "btn_cancel_hover":     "#444444",
        "btn_dark":             "#444444",
        "btn_dark_hover":       "#555555",

        # ── Segments / sélecteurs ─────────────────────────────────────
        "seg_bg":               "#333333",
        "seg_text":             "#aaaaaa",
        "seg_border":           "#555555",
        "seg_hover":            "#444444",
        "seg_active_text":      "#ffffff",

        # ── Scrollbar ─────────────────────────────────────────────────
        "scrollbar_bg":         "#202020",
        "scrollbar_handle":     "#3e3e3e",

        # ── Hover générique ───────────────────────────────────────────
        "hover_card":           "#333333",
        "hover_card_alt":       "#353535",

        # ── Divers ────────────────────────────────────────────────────
        "combo_selection":      "#444444",
        "progress_bg":          "#333333",
        "pbar_bg":              "#252525",
        "arrow_color":          "#ffffff",      # flèche dropdown SVG
        "locked_btn":           "#444444",
        "locked_btn_hover":     "#666666",
        "locked_text":          "#ffffff",
        "preview_text":         "#666666",
        "profile_btn":          "#444444",
        "profile_btn_text":     "#ffffff",
        "stats_text":           "#aaaaaa",
        "tab_border":           "#555555",
        "btn_speed_checked":    "#1f538d",
        "btn_speed_checked_hov":"#2a6dbd",
        "speed_text":           "#aaaaaa",
    },

    # ══════════════════════════════════════════════════════════════════
    #  LIGHT
    # ══════════════════════════════════════════════════════════════════
    "Light": {
        # ── Identificateur ────────────────────────────────────────────
        "suffix":               "_LIGHT",

        # ── Texte ─────────────────────────────────────────────────────
        "text":                 "#111111",
        "text_secondary":       "#555555",
        "text_disabled":        "#aaaaaa",
        "text_code":            "#006600",      # G-Code viewer
        "text_code_dark":       "#00ff00",

        # ── Fonds principaux ──────────────────────────────────────────
        "bg_app":               "#f5f5f5",
        "bg_main":              "#f0f0f0",
        "bg_card":              "#e0e0e0",
        "bg_card_alt":          "#e8e8e8",
        "bg_deep":              "#d8d8d8",
        "bg_entry":             "#ffffff",
        "bg_entry_alt":         "#ffffff",
        "bg_canvas":            "#e0e0e0",
        "bg_scroll":            "#f5f5f5",
        "bg_speed":             "#e8e8e8",
        "bg_speed_btn":         "#d0d0d0",
        "bg_stats":             "#f0f0f0",
        "bg_tabs":              "#f5f5f5",
        "bg_tab":               "#e0e0e0",
        "bg_preview":           "#eeeeee",
        "bg_select":            "#e8e8e8",
        "bg_opts":              "#dedede",

        # ── Bordures ──────────────────────────────────────────────────
        "border":               "#cccccc",
        "border_strong":        "#bbbbbb",
        "border_light":         "#bbbbbb",
        "border_card":          "#cccccc",

        # ── Boutons neutres ───────────────────────────────────────────
        "btn_neutral":          "#cccccc",
        "btn_neutral_hover":    "#b8b8b8",
        "btn_cancel":           "#d0d0d0",
        "btn_cancel_hover":     "#bcbcbc",
        "btn_dark":             "#cccccc",
        "btn_dark_hover":       "#b8b8b8",

        # ── Segments / sélecteurs ─────────────────────────────────────
        "seg_bg":               "#e0e0e0",
        "seg_text":             "#555555",
        "seg_border":           "#bbbbbb",
        "seg_hover":            "#d0d0d0",
        "seg_active_text":      "#111111",

        # ── Scrollbar ─────────────────────────────────────────────────
        "scrollbar_bg":         "#e8e8e8",
        "scrollbar_handle":     "#b0b0b0",

        # ── Hover générique ───────────────────────────────────────────
        "hover_card":           "#dde8f5",
        "hover_card_alt":       "#d8d8d8",

        # ── Divers ────────────────────────────────────────────────────
        "combo_selection":      "#d0e4f7",
        "progress_bg":          "#cccccc",
        "pbar_bg":              "#e8e8e8",
        "arrow_color":          "#111111",      # flèche dropdown SVG
        "locked_btn":           "#bbbbbb",
        "locked_btn_hover":     "#999999",
        "locked_text":          "#111111",
        "preview_text":         "#999999",
        "profile_btn":          "#cccccc",
        "profile_btn_text":     "#222222",
        "stats_text":           "#444444",
        "tab_border":           "#bbbbbb",
        "btn_speed_checked":    "#4a90d9",
        "btn_speed_checked_hov":"#2a6dbd",
        "speed_text":           "#444444",
    },
}


def get_theme(name: str) -> dict:
    """Retourne le dict de couleurs pour le thème demandé.
    Fallback sur Dark si le thème est inconnu."""
    return THEMES.get(name, THEMES["Dark"])
