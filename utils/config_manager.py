import json
import os
import copy

class ConfigManager:
    # Source de vérité unique pour les paramètres d'usine
    DEFAULT_CONFIG = {
        "machine_settings": {
            "theme": "Dark",
            "language": "English",
            "cmd_mode": "M67 (Analog)",
            "firing_mode": "M3/M5",
            "m67_e_num": "0",
            "ctrl_max": "1000",
            "gcode_extension": ".nc",
            "laser_latency": 0.0,
            "premove": 10.0,
            "enable_thumbnails": True,
            "custom_header": "",
            "custom_footer": ""
        },
        "stats": {
            "total_lines": 0,
            "total_gcodes": 0,
            "total_time_seconds": 0.0
        }
    }

    def __init__(self, config_path):
        self.config_path = config_path
        self.data = self._load_from_disk()
        self._apply_defaults()

    def _load_from_disk(self):
        """Charge le fichier JSON ou renvoie un dict vide si absent/corrompu"""
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _apply_defaults(self):
        """Injecte les valeurs par défaut manquantes dans les données chargées"""
        for section, content in self.DEFAULT_CONFIG.items():
            if section not in self.data:
                self.data[section] = copy.deepcopy(content)
            else:
                for key, val in content.items():
                    if key not in self.data[section]:
                        self.data[section][key] = val

    def get_item(self, section, key, default=None):
        """LA MÉTHODE MANQUANTE : Récupère une valeur spécifique"""
        section_data = self.data.get(section, {})
        return section_data.get(key, default)

    def get_section(self, section_name):
        """Récupère une section entière (utile pour SettingsView)"""
        return self.data.get(section_name, {})

    def set_section(self, section_name, new_data):
        """Met à jour une section avant sauvegarde"""
        self.data[section_name] = new_data

    def save(self):
        """Sauvegarde l'état actuel sur le disque"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4)
            return True
        except Exception as e:
            print(f"Erreur de sauvegarde : {e}")
            return False

    def reset_all(self):
        """Réinitialisation totale aux paramètres d'usine"""
        self.data = copy.deepcopy(self.DEFAULT_CONFIG)
        return self.save()