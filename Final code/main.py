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
    
    print(f"[*] Scanner en arrière-plan démarré. Cible : {config.DEFAULT_SUBNET}, Intervalle : {config.SCAN_INTERVAL_SECONDS}s")

    time.sleep(3)

    while True:
        try:
            if config.SIMULATOR_ENABLED:
                for ip_simulee, infos in snmp.SIMULATED_DEVICES.items():
                    database.register_host(ip_simulee, infos["sysName"], "active")

            scanner.scan_subnet(config.DEFAULT_SUBNET)

        except Exception as e:
            print(f"[-] Erreur dans le scanner de sous-réseau : {e}")

        time.sleep(config.SCAN_INTERVAL_SECONDS)


def boucle_snmp_arriere_plan():
  
    print(f"[*] Interrogation SNMP en arrière-plan démarrée. Intervalle : {config.SNMP_POLLING_INTERVAL_SECONDS}s")

    time.sleep(6)

    while True:
        try:
            hotes = database.get_hosts()
            hotes_actifs = [h for h in hotes if h["status"] == "active"]

            for h in hotes_actifs:
                ip = h["ip"]
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
  
    root = tk.Tk()

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
    print("[*] Initialisation de la base de données...")
    database.init_db()

    print("[*] Démarrage des agents SNMP simulés (Socket UDP)...")
    demarrer_agents_simules()

    threading.Thread(target=boucle_scanner_arriere_plan, daemon=True).start()

    threading.Thread(target=boucle_snmp_arriere_plan, daemon=True).start()

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
            print("[*] Application fermée.")
            return

        print("[*] Déconnexion demandée. Retour à l'écran de connexion...")


if __name__ == "__main__":
    main()
