import os
import sys
from PIL import Image, ImageTk

def setup_toplevel_window(window, parent, scale=0.60):
    window.update_idletasks()
    parent.update_idletasks()
    
    # 1. Dimensions du parent
    p_width = parent.winfo_width()
    p_height = parent.winfo_height()
    p_x = parent.winfo_rootx()
    p_y = parent.winfo_rooty()

    # 2. Calcul de la taille cible
    s_width = int(p_width * scale)
    s_height = int(p_height * scale)

    # 3. SÉCURITÉ : On récupère la hauteur RÉELLE de l'écran sans barre des tâches
    # Sous Windows, on peut utiliser cette astuce pour ne pas déborder :
    screen_h = window.winfo_screenheight()
    max_h = screen_h - 100 # Réserve 100px pour la barre des tâches et le titre
    
    if s_height > max_h:
        s_height = max_h

    # 4. Centrage
    pos_x = p_x + (p_width - s_width) // 2
    pos_y = p_y + (p_height - s_height) // 2
    
    # Sécurité pour ne pas coller au bord haut
    if pos_y < 20: pos_y = 20

    window.geometry(f"{s_width}x{s_height}+{pos_x}+{pos_y}")
    window.update_idletasks() # Applique avant que apply_window_icon ne passe
    
    from utils.gui_utils import apply_window_icon
    apply_window_icon(window, parent)

def apply_window_icon(window_instance, parent):
    try:
        # Priorité au chemin du parent
        path = getattr(parent, 'icon_path', None)
        
        # Recalcul du chemin si nécessaire
        if not path or not os.path.exists(path):
            # On part du dossier où se trouve gui_utils.py
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Si gui_utils est dans 'utils/' et assets est à la racine :
            path = os.path.abspath(os.path.join(current_dir, "..", "assets", "icone_alig.ico"))

        if os.path.exists(path):
            # On utilise un délai un peu plus long pour s'assurer que la fenêtre est prête
            window_instance.after(200, lambda: _set_icon_safe(window_instance, path))
        else:
            print(f"DEBUG: Fichier icône introuvable à : {path}")
                
    except Exception as e:
        print(f"Erreur icône : {e}")

def _set_icon_safe(window_instance, path):
    try:
        if sys.platform.startswith('win'):
            window_instance.iconbitmap(path)
        else:
            img = Image.open(path)
            photo = ImageTk.PhotoImage(img)
            # IMPORTANT : Garder une référence pour éviter le Garbage Collector
            window_instance._icon_ref = photo 
            window_instance.wm_iconphoto(True, photo)
    except Exception as e:
        print(f"Erreur application icône : {e}")

def setup_app_id():
    """
    Force Windows à reconnaître l'application comme une entité distincte de Python.
    Indispensable pour que l'icône de la barre des tâches corresponde à l'icône de la fenêtre.
    """
    if sys.platform.startswith('win'):
        try:
            import ctypes
            # Identifiant unique : format 'editeur.logiciel.version'
            myappid = 'alig_project.engraver_v1.0' 
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"Erreur d'initialisation de l'AppID Windows : {e}")

def bind_minimize_sync(window, parent):
    """Synchronise la réduction et la restauration des deux fenêtres."""
    
    def on_parent_state_change(event):
        # On vérifie que c'est bien le parent qui change d'état (pas un enfant)
        if event.widget == parent:
            state = parent.state()
            if state == 'iconic':
                window.withdraw() # Cache la simulation si le main est réduit
            elif state == 'normal':
                window.deiconify() # Réaffiche la simulation si le main revient

    parent.bind("<Unmap>", on_parent_state_change)
    parent.bind("<Map>", on_parent_state_change)