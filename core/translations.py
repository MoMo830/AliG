# core/translations.py

THEMES = ["System", "Dark", "Light"]

TRANSLATIONS = {
    "English": {
        "settings": {
<<<<<<< HEAD
            "title": "SETTINGS",  
            "sec_appearance": "SOFTWARE & INTERFACE", 
=======
            "title": "SETTINGS",  # Changé pour être plus générique
            "sec_appearance": "SOFTWARE & INTERFACE", # Plus explicite pour la 2ème col
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
            "label_theme": "Appearance Mode:",
            "label_lang": "Language:",
            "sec_gcode": "G-CODE & PROTOCOL",
            "label_cmd_mode": "Laser Command Mode:",
            "label_output_e": "M67 Output Number (E):",
            "label_ctrl_max": "Controller Max Value:",
            "label_firing": "Firing Mode:",
            "sec_hardware": "HARDWARE BEHAVIOR",
            "label_latency": "Laser Latency (ms):",
            "label_overscan": "Default Overscan (mm):",
            "sec_scripts": "SYSTEM SCRIPTS",
            "label_header": "Global Header G-Code",
            "label_footer": "Global Footer G-Code",
<<<<<<< HEAD
            "btn_save": "SAVE SETTINGS",
            "msg_success": "Configuration saved successfully!",
            "msg_error_num": "Please verify that all numeric fields contain valid numbers.",
            "enable_thumbnails": "Enable Thumbnails",
            "maintenance_data": "MAINTENANCE & DATA",
            "erase_thumbnails": "Erase thumbnails",
            "erase_thumbnails_confirm": "Erase thumbnails ?",
            "erase_thumbnails_done": "Thumbnails erased !",
            "reset_all_parameters": "Reset all parameters",
            "reset_all_parameters_confirm": "Sure ?",
            "reset_all_parameters_done": "Reset done !",
            "reset_all_parameters_error": "Reset error"
=======
            "btn_save": "SAVE SETTINGS", # Plus court pour le bouton en haut
            "msg_success": "Configuration saved successfully!",
            "msg_error_num": "Please verify that all numeric fields contain valid numbers.",
            "enable_thumbnails": "Enable Thumbnails"
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8

        },
        "dashboard": {
            "raster_title": "IMAGE RASTERING",
            "raster_desc": "Grayscale Photo Engraving.",
            "dithering_title": "DITHERING MODE",
            "dithering_desc": "Converts grayscale into black and white patterns (1-bit). Best for glass or metal engraving.",
            "infill_title": "VECTOR INFILL",
            "infill_desc": "Fill vector paths with G-Code patterns.",
            "calibration_title": "CALIBRATION",
            "calibration_desc": "Run tests for latency, speed and power to optimize your machine settings.",
            "parser_title": "GCODE CHECK",
            "parser_desc": "Use the Gcode parser to check any 2D GcodeFile.\n(Coming Soon)",
            "settings_title": "SETTINGS",
            "settings_desc": "Configure G-Code commands, hardware offsets, and global laser limits.",
            "no_history": "No recent generations found",
            "history": "Recent Generations",
<<<<<<< HEAD
            "machine_stats": "Machine Statistics",
=======
            "machine_stats": "📊 Machine Statistics",
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
            "lines_generated": "Lines Generated",
            "gcode_saved": "G-Codes Saved",
            "total_engraving_time": "Total Engraving Time"
        },
        "topbar": {
            "support": "☕ Support the project",
            "credits": "Developed by Alexandre 'MoMo'",
            "dashboard": "DASHBOARD",
            "raster": "Raster engraving",
            "simulation": "G-Code Simulation",
            "calibration": "Machine Calibration"
        },
        "common": {
            "import_profile": "IMPORT PROFILE",
            "export_profile": "EXPORT PROFILE",
            "geometry": "Geometry",
            "image": "Image",
            "laser": "Laser",
            "Gcode": "G-code",
            "target_width" :"Target Width (mm)",
<<<<<<< HEAD
            "generate_gcode": "GENERATE",
            "target_width": "Target Width (mm)",
            "line_step": "Line Step / Resolution (mm)",
            "force_width": "Force Exact Width",
            "dpi_resolution": "Resolution (DPI)",
            "raster_mode": "Scanning Direction",
            "origin_point": "Origin Point",
            "custom_offset_x": "Custom Offset X (mm)",
            "custom_offset_y": "Custom Offset Y (mm)",
            "contrast": "Contrast Correction",
            "gamma": "Gamma Correction",
            "thermal": "Thermal Correction",
            "invert_color": "Invert Relief (Black ↔ White)",
            "feedrate": "Feedrate (F)",
            "overscan": "Overscan (mm)",
            "min_power": "Min Power (%)",
            "max_power": "Max Power (%)",
            "laser_latency": "Laser Latency (ms)",
            "gray_steps": "Grayscale Steps",
            "cmd_mode": "Laser Command Mode:",
            "m67_output": "M67 Output Number (E):",
            "choose_image": "PLEASE SELECT AN IMAGE\nTO BEGIN",
            "ctrl_max_value": "Controller Max Value:",
            "firing_mode": "Firing Mode:",
            "gcode_header": "Header G-Code",
            "at_start": " (at start)",
            "gcode_footer": "Footer G-Code",
            "before_m30": " (before M30)",
            "point_fram_options": "Pointing & Framing options:",
            "pause_command": "Pause Command:",
            "void_pause": "(empty for no pause)",
            "origin_pointing": "Point Origin (Low power pointer)",
            "framing_option": "Framing",
            "framing_power": "Frame/Pointing Power (%):",
            "framing_ratio": "Framing Speed Ratio:",
            "hint_power": "(Keep low to avoid marking)",
            "confirm_title": "Confirmation",
            "confirm_subtitle": "This action is irreversible.",
            "btn_cancel": "Cancel",
            "btn_confirm": "Confirm"
=======
            "generate_gcode": "GENERATE"
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
        }
    },
    "Français": {
        "settings": {
            "title": "RÉGLAGES", # Changé
<<<<<<< HEAD
            "sec_appearance": "LOGICIEL & INTERFACE", 
=======
            "sec_appearance": "LOGICIEL & INTERFACE", # Changé
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
            "label_theme": "Mode d'apparence :",
            "label_lang": "Langue :",
            "sec_gcode": "G-CODE & PROTOCOLE",
            "label_cmd_mode": "Mode commande laser :",
            "label_output_e": "Numéro sortie M67 (E) :",
            "label_ctrl_max": "Valeur max contrôleur :",
            "label_firing": "Mode d'allumage :",
            "sec_hardware": "COMPORTEMENT MATÉRIEL",
            "label_latency": "Latence laser (ms) :",
            "label_overscan": "Overscan par défaut (mm) :",
            "sec_scripts": "SCRIPTS SYSTÈME",
            "label_header": "G-Code d'en-tête global",
            "label_footer": "G-Code de fin global",
            "btn_save": "SAUVEGARDER", # Plus court
            "msg_success": "Configuration enregistrée avec succès !",
            "msg_error_num": "Veuillez vérifier que les champs numériques sont valides.",
<<<<<<< HEAD
            "enable_thumbnails": "Autoriser la création de vignettes",
            "maintenance_data": "MAINTENANCE & DONNÉES",
            "erase_thumbnails": "Effacer les vignettes",
            "erase_thumbnails_confirm": "Effacer les vignettes ?",
            "erase_thumbnails_done": "Vignettes & Stats effacées !",
            "reset_all_parameters": "Réinitialiser tous les paramètres",
            "reset_all_parameters_confirm": "Réinitialiser tout ?",
            "reset_all_parameters_done": "Configuration réinitialisée !",
            "reset_all_parameters_error": "Erreur durant la réinitialisation"
=======
            "enable_thumbnails": "Autoriser la création de vignettes"

>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
        },
        "dashboard": {
            "raster_title": "GRAVURE RASTER",
            "raster_desc": "Gravure de photos en niveaux de gris.",
            "dithering_title": "DITHERING (TRAMAGE)",
            "dithering_desc": "Convertit les nuances de gris en points noirs (1-bit). Idéal pour les gravures sur verre ou métal.",
            "infill_title": "REMPLISSAGE VECTORIEL",
            "infill_desc": "Remplit les tracés vectoriels avec des motifs de G-Code (hachurage).",
            "calibration_title": "CALIBRAGE",
            "calibration_desc": "Réglage des décalages et de la puissance.",
            "parser_title": "Vérificateur de GCODE",
            "parser_desc": "Utilisez le parseur G-code pour vérifier n'importe quel fichier G-code 2D.\n(Prochainement)",
            "settings_title": "REGLAGES",
            "settings_desc": "Configurez les commandes G-Code, les décalages matériels et les limites globales du laser.",
            "no_history": "Aucune génération récente",
            "history": "Générations récentes",
<<<<<<< HEAD
            "machine_stats": "Statistiques",
=======
            "machine_stats": "📊 Statistiques",
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
            "lines_generated": "Lignes générées",
            "gcode_saved": "G-Codes sauvegardés",
            "total_engraving_time": "Temps total de gravure"
        },
        "topbar": {
            "support": "☕ Soutenir le projet",
<<<<<<< HEAD
            "credits": "Développé par Alexandre 'MoMo'",
=======
            "credits": "Developpé par Alexandre 'MoMo'",
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
            "dashboard": "Tableau de bord",
            "raster": "Gravure en boustrophédon",
            "simulation": "Simulation de G-Code",
            "calibration": "Calibrage machine"
        },
        "common": {
<<<<<<< HEAD
            "import_profile": "Importer un profil",
            "export_profile": "Exporter un profil",
            "geometry": "Géometrie",
=======
            "import_profile": "Import de profil",
            "export_profile": "Export de profil",
            "geometry": "Geometrie",
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
            "image": "Image",
            "laser": "Laser",
            "Gcode": "G-code",
            "target_width" :"Largeur cible (mm)",
<<<<<<< HEAD
            "generate_gcode": "GENERER",
            "target_width": "Largeur cible (mm)",
            "line_step": "Résolution inter-lignes (mm)",
            "force_width": "Forcer largeur exacte",
            "dpi_resolution": "Résolution (DPI)",
            "raster_mode": "Sens de déplacement",
            "origin_point": "Origine",
            "custom_offset_x": "Décalage origine X (mm)",
            "custom_offset_y": "Décalage origine Y (mm)",
            "contrast": "Correction de contraste",
            "gamma": "Correction gamma",
            "thermal": "Correction thermique",
            "invert_color": "Inversion de couleurs (noir ↔ blanc)",
            "feedrate": "Vitesse d'avance (F)",
            "overscan": "Dépassement (mm)",
            "min_power": "Puissance Min (%)",
            "max_power": "Puissance Max (%)",
            "laser_latency": "Latence Laser (ms)",
            "gray_steps": "Niveaux de gris",
            "cmd_mode": "Mode de commande laser :",
            "m67_output": "Numéro de sortie M67 (E) :",
            "choose_image": "VEUILLEZ SELECTIONNER UNE IMAGE\nPOUR COMMENCER",
            "ctrl_max_value": "Pleine échelle de controleur :",
            "firing_mode": "Mode de commande :",
            "gcode_header": "entête de G-Code", #accent
            "at_start": " (au début)",
            "gcode_footer": "Pied de  G-Code",
            "before_m30": " (avant M30)",
            "point_fram_options": "Option de pointage & cadrage :",
            "pause_command": "Commande de pause :",
            "void_pause": "(vide = pas de pause)",
            "origin_pointing": "Pointage d'origine",
            "framing_option": "Encadrement",
            "framing_power": "Puisance encadrement/pointage (%)",
            "framing_ratio": "Ratio de vitesse d'encadrement :",
            "hint_power": "(Laisser bas pour éviter le marquage)",
            "confirm_title": "Confirmation",
            "confirm_subtitle": "Cette action est irréversible.",
            "btn_cancel": "Annuler",
            "btn_confirm": "Confirmer"
            }
=======
            "generate_gcode": "GENERER"
        }
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
    }
}