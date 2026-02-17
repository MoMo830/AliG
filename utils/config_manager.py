import json
import os

class ConfigManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.full_config = self.load_all()

    def load_all(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {} # Retourne un dico vide si le fichier n'existe pas

    def get_section(self, section_name):
        """Retourne une sous-section (ex: 'machine_settings' ou 'raster_mode')"""
        return self.full_config.get(section_name, {})

    def set_section(self, section_name, data):
        """Met à jour une section sans toucher aux autres"""
        if section_name not in self.full_config:
            self.full_config[section_name] = {}
        self.full_config[section_name].update(data)

    def save(self):
        """Écrit tout le dictionnaire dans le fichier JSON unique"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.full_config, f, indent=4)
            return True
        except Exception as e:
            print(f"Erreur sauvegarde : {e}")
            return False