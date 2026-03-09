#!/usr/bin/env python3
import socket
import threading
import os
import json
import struct
import argparse
import sys
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TransferSpeedColumn, TimeRemainingColumn

# Configuration
TCP_PORT = 9000
UDP_PORT = 9001
BUFFER_SIZE = 4096
console = Console()

class EduDrop:
    def __init__(self, target_ip=None):
        self.target_ip = target_ip
        self.running = True
        
        # Configuration UDP (Chat & Découverte)
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Bind sur 0.0.0.0 permet d'écouter sur toutes les interfaces
        self.udp_sock.bind(('', UDP_PORT))
        
        # Configuration TCP (Transfert de fichiers)
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.bind(('', TCP_PORT))
        self.tcp_sock.listen(5)

    def start(self):
        # Lancement des threads d'écoute en arrière-plan
        threading.Thread(target=self.listen_udp, daemon=True).start()
        threading.Thread(target=self.listen_tcp, daemon=True).start()
        
        console.print(f"[bold green]EduDrop Démarré.[/bold green]")
        console.print(f"Écoute sur TCP:{TCP_PORT} / UDP:{UDP_PORT}")
        
        if self.target_ip:
            console.print(f"Cible IP définie : [cyan]{self.target_ip}[/cyan]")
        else:
            console.print("[yellow]Aucune IP cible définie. Utilisez 'setip <IP>' ou le mode broadcast pour le chat.[/yellow]")
        
        self.input_loop()

    def input_loop(self):
        console.print("[dim]Commandes : send <fichier>, chat <msg>, setip <ip>, exit[/dim]")
        while self.running:
            try:
                cmd_input = input(">> ").strip()
                if not cmd_input:
                    continue
                
                parts = cmd_input.split()
                action = parts[0].lower()
                
                if action == "send" and len(parts) > 1:
                    filepath = parts[1]
                    if os.path.exists(filepath):
                        self.send_file(filepath)
                    else:
                        console.print(f"[red]Fichier introuvable : {filepath}[/red]")
                
                elif action == "chat" and len(parts) > 1:
                    msg = " ".join(parts[1:])
                    self.send_chat(msg)
                
                elif action == "setip" and len(parts) > 1:
                    self.target_ip = parts[1]
                    console.print(f"[yellow]IP cible mise à jour : {self.target_ip}[/yellow]")
                
                elif action == "help":
                    console.print("Commandes : send <fichier>, chat <msg>, setip <ip>, exit")
                
                elif action == "exit":
                    self.running = False
                    console.print("[bold red]Arrêt...[/bold red]")
                    sys.exit(0)
                
                else:
                    console.print("[red]Commande inconnue.[/red]")
            
            except KeyboardInterrupt:
                self.running = False
                sys.exit(0)
            except Exception as e:
                console.print(f"[red]Erreur : {e}[/red]")

    def listen_udp(self):
        while self.running:
            try:
                data, addr = self.udp_sock.recvfrom(BUFFER_SIZE)
                # Éviter de recevoir ses propres messages broadcastés
                # Note: Pour une vraie prod, filtrer par IP locale, ici simplifié.
                message = json.loads(data.decode('utf-8'))
                if message.get('type') == 'chat':
                    console.print(f"\n[blue][CHAT {addr[0]}][/blue] {message['payload']}")
            except Exception:
                pass

    def send_chat(self, text):
        payload = json.dumps({"type": "chat", "payload": text}).encode('utf-8')
        try:
            if self.target_ip:
                self.udp_sock.sendto(payload, (self.target_ip, UDP_PORT))
            else:
                self.udp_sock.sendto(payload, ('<broadcast>', UDP_PORT))
        except PermissionError:
            console.print("[red]Erreur: Permission refusée pour le broadcast (vérifiez votre réseau/pare-feu).[/red]")
        except Exception as e:
            console.print(f"[red]Erreur d'envoi chat: {e}[/red]")

    def listen_tcp(self):
        while self.running:
            try:
                conn, addr = self.tcp_sock.accept()
                threading.Thread(target=self.handle_incoming_file, args=(conn, addr), daemon=True).start()
            except Exception:
                pass

    def handle_incoming_file(self, conn, addr):
        try:
            # 1. Lire la taille du header (4 bytes int)
            header_size_data = conn.recv(4)
            if not header_size_data:
                return
            
            header_size = struct.unpack('!I', header_size_data)[0]
            
            # 2. Lire le header (JSON metadata)
            header_data = conn.recv(header_size)
            metadata = json.loads(header_data.decode('utf-8'))
            
            filename = os.path.basename(metadata['filename'])
            filesize = metadata['size']
            
            console.print(f"\n[bold magenta]Réception de {filename} ({filesize} bytes) depuis {addr[0]}...[/bold magenta]")
            
            received = 0
            output_filename = f"received_{filename}"
            
            with open(output_filename, 'wb') as f:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn(),
                    console=console
                ) as progress:
                    task = progress.add_task("Téléchargement...", total=filesize)
                    
                    while received < filesize:
                        chunk = conn.recv(min(BUFFER_SIZE, filesize - received))
                        if not chunk:
                            break
                        f.write(chunk)
                        received += len(chunk)
                        progress.update(task, advance=len(chunk))
            
            console.print(f"[bold green]Transfert terminé : {output_filename}[/bold green]")
            
        except Exception as e:
            console.print(f"[red]Échec du transfert : {e}[/red]")
        finally:
            conn.close()

    def send_file(self, filepath):
        if not self.target_ip:
            console.print("[red]IP cible non définie. Utilisez 'setip <ip>'[/red]")
            return

        try:
            filesize = os.path.getsize(filepath)
            filename = os.path.basename(filepath)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10) # Timeout de connexion
            
            console.print(f"[cyan]Connexion à {self.target_ip}...[/cyan]")
            sock.connect((self.target_ip, TCP_PORT))
            
            # Préparation du header
            metadata = json.dumps({"filename": filename, "size": filesize}).encode('utf-8')
            # Envoi taille du header + header
            sock.send(struct.pack('!I', len(metadata)))
            sock.send(metadata)
            
            sent = 0
            with open(filepath, 'rb') as f:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn(),
                    console=console
                ) as progress:
                    task = progress.add_task("Envoi...", total=filesize)
                    
                    while sent < filesize:
                        chunk = f.read(BUFFER_SIZE)
                        if not chunk:
                            break
                        sock.sendall(chunk)
                        sent += len(chunk)
                        progress.update(task, advance=len(chunk))
            
            console.print("[bold green]Fichier envoyé avec succès.[/bold green]")
            sock.close()
            
        except socket.timeout:
            console.print("[red]Délai d'attente dépassé (Timeout). La cible est-elle active ?[/red]")
        except ConnectionRefusedError:
            console.print("[red]Connexion refusée par la cible.[/red]")
        except Exception as e:
            console.print(f"[red]Erreur d'envoi : {e}[/red]")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EduDrop - Outil de transfert P2P local")
    parser.add_argument("--target", help="Adresse IP de la cible (optionnel)")
    args = parser.parse_args()
    
    app = EduDrop(target_ip=args.target)
    app.start()