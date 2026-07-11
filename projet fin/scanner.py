"""
scanner.py
==========
Detection et suivi des adresses IP actives sur le sous-reseau (ping
sweep). C'est ce module qui alimente la table 'equipement' et la
table 'presence' (connexions / deconnexions) dans la base de donnees.
"""

import subprocess
import platform
import socket
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
import config
import database


def ping_host(ip):
    """
    Envoie un ping a une adresse IP et retourne (ip, actif, nom_hote).
    Le succes est detecte par la presence de 'ttl=' dans la reponse.
    """
    type_systeme = platform.system().lower()

    if type_systeme == "windows":
        # Commande ping Windows : -n 1 (1 paquet), -w PING_TIMEOUT_MS (delai en ms)
        commande = ["ping", "-n", "1", "-w", str(config.PING_TIMEOUT_MS), ip]
    else:
        # Commande ping Linux/macOS : -c 1 (1 paquet), -W delai (en secondes)
        delai_sec = str(max(1, config.PING_TIMEOUT_MS // 1000))
        commande = ["ping", "-c", "1", "-W", delai_sec, ip]

    try:
        resultat = subprocess.run(commande, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1.5)
        sortie = resultat.stdout.lower()

        # 'ttl=' est present dans une reponse de ping reussie
        est_actif = (resultat.returncode == 0) and ("ttl=" in sortie)
    except Exception:
        est_actif = False

    nom_hote = None
    if est_actif:
        try:
            nom_hote, _, _ = socket.gethostbyaddr(ip)
        except Exception:
            nom_hote = "Hôte inconnu"

    return ip, est_actif, nom_hote


def scan_subnet(sous_reseau_str, progress_callback=None):
    """
    Analyse un sous-reseau donne (ex: 192.168.1.0/24) en parallele.
    Appelle progress_callback(courant, total) pour suivre l'avancement.
    Retourne une liste de tuples (ip, actif, nom_hote).
    """
    try:
        reseau = ipaddress.ip_network(sous_reseau_str, strict=False)
        hotes = list(reseau.hosts())
    except Exception as e:
        print(f"[-] Erreur d'analyse du sous-réseau {sous_reseau_str} : {e}")
        return []

    total_hotes = len(hotes)
    if total_hotes == 0:
        return []

    resultats = []
    termines = 0

    # Scan en parallele avec un pool de threads
    with ThreadPoolExecutor(max_workers=config.MAX_SCAN_THREADS) as executor:
        taches = {executor.submit(ping_host, str(ip)): str(ip) for ip in hotes}

        for tache in as_completed(taches):
            try:
                ip, actif, nom_hote = tache.result()
                resultats.append((ip, actif, nom_hote))

                # Enregistrement en base de donnees en temps reel
                statut = "active" if actif else "inactive"
                database.register_host(ip, nom_hote, statut)

            except Exception as e:
                print(f"[-] Erreur lors du scan de l'hôte : {e}")

            termines += 1
            if progress_callback:
                progress_callback(termines, total_hotes)

    return resultats
