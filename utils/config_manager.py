import json
import os

class ConfigManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.full_config = self.load_all()

    def load_all(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erreur lecture config : {e}")
        return {}

    # --- NOUVELLES MÉTHODES RÉCLAMÉES ---

    def get_item(self, section, key, default=None):
        """Récupère une valeur précise dans une section."""
        section_data = self.get_section(section)
        return section_data.get(key, default)

    def set_item(self, section, key, value):
        """Définit une valeur unique dans une section sans écraser le reste."""
        if section not in self.full_config:
            self.full_config[section] = {}
        self.full_config[section][key] = value

    # ---------------------------------------

    def get_section(self, section_name):
        return self.full_config.get(section_name, {})

    def set_section(self, section_name, data):
        self.full_config[section_name] = data

    def save(self):
        try:
<<<<<<< HEAD
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.full_config, f, indent=4, default=lambda o: float(o) if hasattr(o, '__float__') else str(o))
=======
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.full_config, f, indent=4)
>>>>>>> ffa54c99651cc0108bcb6eba663d7aacba5dc4b8
            return True
        except Exception as e:
            print(f"Erreur sauvegarde : {e}")
            return False
        
    def reset_all(self):
        """Vide totalement la configuration en mémoire et sur le disque."""
        self.full_config = {}  # On vide la mémoire (crucial pour arrêter l'héritage)
        try:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
            # On recrée immédiatement un fichier vide propre pour éviter les erreurs de lecture
            return self.save()
        except Exception as e:
            print(f"Erreur lors du reset physique : {e}")
            return False

    # --- MÉTHODES DE VALIDATION ---
    @staticmethod
    def is_valid_file(path):
        return bool(path and isinstance(path, str) and os.path.isfile(path))

    @staticmethod
    def validate_image_path(path):
        if not ConfigManager.is_valid_file(path):
            return ""
        extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
        ext = os.path.splitext(path)[1].lower()
        return path if ext in extensions else ""
    
