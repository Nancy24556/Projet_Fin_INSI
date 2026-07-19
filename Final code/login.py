import tkinter as tk
from tkinter import messagebox
import database

COLOR_BG = "#121212"
COLOR_CARD = "#1E1E1E"
COLOR_HOVER = "#2C2C2C"
COLOR_TEXT = "#FFFFFF"
COLOR_TEXT_MUTED = "#A0A0A0"
COLOR_ACCENT = "#00ADB5"
COLOR_SUCCESS = "#2ECA7F"
COLOR_DANGER = "#FF2E93"


class LoginWindow:
   
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SNMP NetSupervisor - Connexion")
        self.root.geometry("420x480")
        self.root.resizable(False, False)
        self.root.configure(bg=COLOR_BG)

        self.logged_user = None
        self.mode = "login"

        self._build_ui()

        self.root.update_idletasks()
        w, h = 420, 480
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        card = tk.Frame(self.root, bg=COLOR_CARD, padx=30, pady=30)
        card.pack(fill="both", expand=True, padx=20, pady=20)

        self.lbl_title = tk.Label(card, text="🔌 SNMP NetSupervisor",
                                   fg=COLOR_TEXT, bg=COLOR_CARD, font=("Segoe UI", 16, "bold"))
        self.lbl_title.pack(pady=(0, 5))

        self.lbl_subtitle = tk.Label(card, text="Connexion", fg=COLOR_TEXT_MUTED,
                                      bg=COLOR_CARD, font=("Segoe UI", 10))
        self.lbl_subtitle.pack(pady=(0, 20))

        self.lbl_nom = tk.Label(card, text="Nom", fg=COLOR_TEXT_MUTED, bg=COLOR_CARD,
                                 font=("Segoe UI", 9), anchor="w")
        self.entry_nom = tk.Entry(card, bg=COLOR_BG, fg=COLOR_TEXT, insertbackground=COLOR_TEXT,
                                   bd=0, highlightthickness=1, highlightcolor=COLOR_ACCENT,
                                   highlightbackground="#444444", font=("Segoe UI", 10))

        self.lbl_email = tk.Label(card, text="Email", fg=COLOR_TEXT_MUTED, bg=COLOR_CARD,
                                   font=("Segoe UI", 9), anchor="w")
        self.lbl_email.pack(fill="x")
        self.entry_email = tk.Entry(card, bg=COLOR_BG, fg=COLOR_TEXT, insertbackground=COLOR_TEXT,
                                     bd=0, highlightthickness=1, highlightcolor=COLOR_ACCENT,
                                     highlightbackground="#444444", font=("Segoe UI", 10))
        self.entry_email.pack(fill="x", ipady=8, pady=(2, 12))

        tk.Label(card, text="Mot de passe", fg=COLOR_TEXT_MUTED, bg=COLOR_CARD,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x")
        self.entry_password = tk.Entry(card, bg=COLOR_BG, fg=COLOR_TEXT, insertbackground=COLOR_TEXT,
                                        bd=0, highlightthickness=1, highlightcolor=COLOR_ACCENT,
                                        highlightbackground="#444444", font=("Segoe UI", 10), show="•")
        self.entry_password.pack(fill="x", ipady=8, pady=(2, 20))
        self.entry_password.bind("<Return>", lambda e: self._on_submit())

        self.btn_submit = tk.Button(card, text="Se connecter", command=self._on_submit,
                                     bg=COLOR_ACCENT, fg="#000000", bd=0, font=("Segoe UI", 10, "bold"),
                                     activebackground=COLOR_SUCCESS, cursor="hand2", pady=8)
        self.btn_submit.pack(fill="x", pady=(0, 12))

        self.lbl_error = tk.Label(card, text="", fg=COLOR_DANGER, bg=COLOR_CARD,
                                   font=("Segoe UI", 9), wraplength=340, justify="center")
        self.lbl_error.pack(pady=(0, 8))

        self.btn_toggle = tk.Button(card, text="Pas encore de compte ? Creer un compte",
                                     command=self._toggle_mode, bg=COLOR_CARD, fg=COLOR_ACCENT,
                                     bd=0, font=("Segoe UI", 9, "underline"), cursor="hand2",
                                     activebackground=COLOR_CARD)
        self.btn_toggle.pack()

        hint = tk.Label(card, text="Compte par defaut : admin@local / admin123",
                         fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, font=("Segoe UI", 8, "italic"))
        hint.pack(side="bottom", pady=(20, 0))

    def _toggle_mode(self):
        self.lbl_error.config(text="")
        if self.mode == "login":
            self.mode = "signup"
            self.lbl_subtitle.config(text="Creer un compte")
            self.btn_submit.config(text="Creer un compte")
            self.btn_toggle.config(text="Deja un compte ? Se connecter")
            self.lbl_nom.pack(fill="x", before=self.lbl_email)
            self.entry_nom.pack(fill="x", ipady=8, pady=(2, 12), before=self.lbl_email)
        else:
            self.mode = "login"
            self.lbl_subtitle.config(text="Connexion")
            self.btn_submit.config(text="Se connecter")
            self.btn_toggle.config(text="Pas encore de compte ? Creer un compte")
            self.lbl_nom.pack_forget()
            self.entry_nom.pack_forget()

    def _on_submit(self):
        email = self.entry_email.get().strip()
        password = self.entry_password.get()

        if not email or not password:
            self.lbl_error.config(text="Veuillez remplir l'email et le mot de passe.")
            return

        if self.mode == "signup":
            nom = self.entry_nom.get().strip()
            if not nom:
                self.lbl_error.config(text="Veuillez indiquer votre nom.")
                return
            success, message = database.create_user(nom, email, password)
            if not success:
                self.lbl_error.config(text=message)
                return
            messagebox.showinfo("Compte cree", "Compte cree avec succes. Vous pouvez vous connecter.")
            self._toggle_mode()
            self.entry_password.delete(0, tk.END)
            return

        success, user = database.verify_login(email, password)
        if not success:
            self.lbl_error.config(text="Email ou mot de passe incorrect.")
            return

        self.logged_user = user
        self.root.destroy()

    def run(self):
       
        self.root.mainloop()
        return self.logged_user
