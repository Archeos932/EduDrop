# EduDrop

Outil CLI minimaliste pour le transfert de fichiers P2P et le chat sur réseau local (LAN/Eduroam).

## Installation

1. Assurez-vous d'avoir Python 3 installé.
2. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

## Utilisation

Lancer l'outil :
```bash
python edudrop.py
# OU si vous voulez spécifier l'IP cible directement
python edudrop.py --target 192.168.1.15
```

### Commandes disponibles dans l'interface

*   `setip <IP>` : Définit l'adresse IP de la machine cible (nécessaire pour l'envoi de fichiers).
*   `chat <message>` : Envoie un message. Si aucune IP n'est définie, le message est envoyé en broadcast (UDP).
*   `send <chemin_du_fichier>` : Envoie un fichier à l'IP cible via TCP.
*   `exit` : Quitter.

## Architecture

*   **TCP (Port 9000)** : Transfert de fichiers fiable.
*   **UDP (Port 9001)** : Chat et découverte (Broadcast).