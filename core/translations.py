# core/translations.py

THEMES = ["System", "Dark", "Light"]

TRANSLATIONS = {
    "English": {
        "settings": {
            "title": "SETTINGS",  # Changé pour être plus générique
            "sec_appearance": "SOFTWARE & INTERFACE", # Plus explicite pour la 2ème col
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
            "btn_save": "SAVE SETTINGS", # Plus court pour le bouton en haut
            "msg_success": "Configuration saved successfully!",
            "msg_error_num": "Please verify that all numeric fields contain valid numbers."
        },
        "dashboard": {
            "raster_title": "IMAGE RASTERING",
            "raster_desc": "Grayscale Photo Engraving.",
            "calibration_title": "CALIBRATION",
            "calibration_desc": "Run tests for latency, speed and power to optimize your machine settings.",
            "parser_title": "GCODE CHECK",
            "parser_desc": "Use the Gcode parser to check any 2D GcodeFile.\n(Coming Soon)",
            "settings_title": "SETTINGS",
            "settings_desc": "Configure G-Code commands, hardware offsets, and global laser limits."
        }
    },
    "Français": {
        "settings": {
            "title": "RÉGLAGES", # Changé
            "sec_appearance": "LOGICIEL & INTERFACE", # Changé
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
            "msg_error_num": "Veuillez vérifier que les champs numériques sont valides."
        },
        "dashboard": {
            "raster_title": "GRAVURE RASTER",
            "raster_desc": "Gravure de photos en niveaux de gris.",
            "calibration_title": "CALIBRAGE",
            "calibration_desc": "Réglage des décalages et de la puissance.",
            "parser_title": "Vérificateur de GCODE",
            "parser_desc": "Utilisez le parseur G-code pour vérifier n'importe quel fichier G-code 2D.\n(Prochainement)",
            "settings_title": "REGLAGES",
            "settings_desc": "Configurez les commandes G-Code, les décalages matériels et les limites globales du laser."
        }
    }
}