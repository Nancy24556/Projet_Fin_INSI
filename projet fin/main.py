import threading
import time
import tkinter as tk

import agent
import config
import database
import scanner
import snmp
from interface import NetworkSupervisionApp
from login import LoginWindow


def demarrer_agents_simules():
    """
    Demarre un agent SNMP (Socket UDP, voir agent.py) pour chaque
    equipement simule defini dans snmp.SIMULATED_DEVICES. Chaque agent
    tourne dans son propre thread et repond aux requetes du
    gestionnaire (snmp.query_snmp_device) exactement comme le ferait
    un agent installe sur une machine reelle du reseau.
    """
    if not config.SIMULATOR_ENABLED:
        return

    for ip, infos in snmp.SIMULATED_DEVICES.items():
        agent.demarrer_agent_local(
            port=infos["port"],
            nom=infos["sysName"],
            description=infos["sysDescr"],
            emplacement=infos["sysLocation"],
            contact=infos["sysContact"],
            host=config.SIMULATOR_HOST,
        )


def boucle_scanner_arriere_plan():
    """
    Analyse periodiquement le sous-reseau configure pour detecter les
    nouveaux equipements ainsi que les changements de connexion/
    deconnexion (table 'presence').
    """
    print(f"[*] Scanner en arrière-plan démarré. Cible : {config.DEFAULT_SUBNET}, Intervalle : {config.SCAN_INTERVAL_SECONDS}s")

    # Attendre quelques secondes le temps d'initialiser la base de donnees
    time.sleep(3)

    while True:
        try:
            # Si le simulateur est active, enregistrer les agents simules comme actifs
            if config.SIMULATOR_ENABLED:
                for ip_simulee, infos in snmp.SIMULATED_DEVICES.items():
                    database.register_host(ip_simulee, infos["sysName"], "active")

            # Analyser le sous-reseau reellement configure
            scanner.scan_subnet(config.DEFAULT_SUBNET)

        except Exception as e:
            print(f"[-] Erreur dans le scanner de sous-réseau : {e}")

        time.sleep(config.SCAN_INTERVAL_SECONDS)


def boucle_snmp_arriere_plan():
    """
    Interroge periodiquement (via le gestionnaire, snmp.py) les
    agents actifs pour mettre a jour leur telemetrie, et archive
    chaque releve (horodatage inclus) dans la base de donnees.
    """
    print(f"[*] Interrogation SNMP en arrière-plan démarrée. Intervalle : {config.SNMP_POLLING_INTERVAL_SECONDS}s")

    # Attendre quelques secondes le temps du scan initial
    time.sleep(6)

    while True:
        try:
            hotes = database.get_hosts()
            hotes_actifs = [h for h in hotes if h["status"] == "active"]

            for h in hotes_actifs:
                ip = h["ip"]
                # Le gestionnaire interroge l'agent via Socket (repli SNMP reel si besoin)
                resultat = snmp.query_snmp_device(ip)
                if resultat:
                    sys_name = resultat.get(config.OIDS["sysName"], "Inconnu")
                    sys_descr = resultat.get(config.OIDS["sysDescr"], "Inconnu")
                    sys_uptime = resultat.get(config.OIDS["sysUpTime"], "Inconnu")
                    sys_location = resultat.get(config.OIDS["sysLocation"], "Inconnu")
                    sys_contact = resultat.get(config.OIDS["sysContact"], "Inconnu")

                    database.add_snmp_record(ip, sys_name, sys_descr, sys_uptime, sys_location, sys_contact)
                    print(f"[+] Télémétrie récupérée avec succès pour {ip} (via l'agent Socket)")
                else:
                    if h["is_snmp_enabled"] == 1:
                        print(f"[-] Échec de l'interrogation de l'agent précédemment actif : {ip}")

        except Exception as e:
            print(f"[-] Erreur dans la boucle SNMP en arrière-plan : {e}")

        time.sleep(config.SNMP_POLLING_INTERVAL_SECONDS)


def lancer_interface_graphique(utilisateur_connecte):
    """
    Construit et affiche la fenetre principale pour l'utilisateur
    donne. Retourne True si l'utilisateur a demande a se deconnecter
    (pour qu'un autre utilisateur puisse se connecter), False s'il a
    ferme l'application.
    """
    root = tk.Tk()

    # Centrer la fenetre sur l'ecran de l'utilisateur
    largeur_fenetre = 1100
    hauteur_fenetre = 700
    largeur_ecran = root.winfo_screenwidth()
    hauteur_ecran = root.winfo_screenheight()
    x = (largeur_ecran - largeur_fenetre) // 2
    y = (hauteur_ecran - hauteur_fenetre) // 2
    root.geometry(f"{largeur_fenetre}x{hauteur_fenetre}+{x}+{y}")

    app = NetworkSupervisionApp(root, utilisateur_connecte)
    root.mainloop()

    return app.demande_deconnexion


def main():
    # 1. Initialiser les tables de la base de donnees SQLite
    print("[*] Initialisation de la base de données...")
    database.init_db()

    # 2. Demarrer les agents SNMP simules (communication par Socket)
    print("[*] Démarrage des agents SNMP simulés (Socket UDP)...")
    demarrer_agents_simules()

    # 3. Demarrer le thread de surveillance de presence sur le sous-reseau
    threading.Thread(target=boucle_scanner_arriere_plan, daemon=True).start()

    # 4. Demarrer le thread du gestionnaire SNMP (interrogation des agents)
    threading.Thread(target=boucle_snmp_arriere_plan, daemon=True).start()

    # 5. Boucle connexion / deconnexion : permet a plusieurs utilisateurs
    #    de se succeder sur le meme poste sans relancer tout le programme.
    while True:
        print("[*] En attente de l'authentification...")
        utilisateur_connecte = LoginWindow().run()
        if utilisateur_connecte is None:
            print("[*] Connexion annulée. Fermeture.")
            return

        print(f"[*] Connecté en tant que : {utilisateur_connecte.get('nom')} ({utilisateur_connecte.get('email')})")

        print("[*] Lancement de l'interface graphique...")
        veut_se_deconnecter = lancer_interface_graphique(utilisateur_connecte)

        if not veut_se_deconnecter:
            # Fermeture normale de l'application (pas une simple deconnexion)
            print("[*] Application fermée.")
            return

        print("[*] Déconnexion demandée. Retour à l'écran de connexion...")


if __name__ == "__main__":
    main()
