# nas_gui_smb.py
import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json


class NASApiAdapter:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self):
        return {"X-API-Key": self.api_key} if self.api_key else {}

    def setup(
        self,
        host: str,
        share: str,
        username: str,
        password: str,
        base_subdir: str,
        retention_days: int,
        domain: str | None,
    ):
        url = f"{self.base_url}/nas/setup"
        payload = {
            "host": host,
            "share": share,
            "username": username,
            "password": password,
            "base_subdir": base_subdir,
            "retention_days": int(retention_days),
            "domain": domain or None,
        }
        r = requests.post(url, json=payload, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def health(self):
        url = f"{self.base_url}/nas/health"
        r = requests.get(url, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    def upload_run(self, run_id: str):
        url = f"{self.base_url}/runs/{run_id}/upload"
        r = requests.post(url, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()


class NASSetupGUI(tk.Toplevel):
    def __init__(self, master: tk.Misc | None = None):
        root_window = None
        if master is None:
            root_window = tk.Tk()
            root_window.withdraw()
            super().__init__(root_window)
        else:
            super().__init__(master)
        self._root_window = root_window
        self.title("NAS Setup (SMB/CIFS)")
        self.geometry("560x520")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # API connection
        frm_api = ttk.LabelFrame(self, text="API Connection")
        frm_api.pack(fill="x", padx=10, pady=8)
        self.var_base = tk.StringVar(value="http://10.19.2.97:8000")
        self.var_key = tk.StringVar(value="")
        ttk.Label(frm_api, text="Base URL:").grid(
            row=0, column=0, sticky="e", padx=5, pady=4
        )
        ttk.Entry(frm_api, textvariable=self.var_base, width=44).grid(
            row=0, column=1, sticky="we", padx=5, pady=4
        )
        ttk.Label(frm_api, text="X-API-Key:").grid(
            row=1, column=0, sticky="e", padx=5, pady=4
        )
        ttk.Entry(frm_api, textvariable=self.var_key, width=44, show="*").grid(
            row=1, column=1, sticky="we", padx=5, pady=4
        )
        frm_api.columnconfigure(1, weight=1)

        # NAS Setup (SMB)
        frm_setup = ttk.LabelFrame(self, text="NAS Access (SMB)")
        frm_setup.pack(fill="x", padx=10, pady=8)
        self.var_host = tk.StringVar(value="10.19.2.25")
        self.var_share = tk.StringVar(value="experiments")  # SMB-Share Name
        self.var_user = tk.StringVar(value="schindlerlab")
        self.var_pass = tk.StringVar(value="Removed-Hybrid4-Upriver")
        self.var_subdir = tk.StringVar(value="")  # optional innerhalb des Shares
        self.var_ret = tk.StringVar(value="14")
        self.var_domain = tk.StringVar(value="")  # optional

        fields = [
            ("Host/IP:", self.var_host, None),
            ("Share:", self.var_share, None),
            ("Username:", self.var_user, None),
            ("Password:", self.var_pass, "*"),
            ("Base Subdir:", self.var_subdir, None),
            ("Retention (Days):", self.var_ret, None),
            ("Domain (optional):", self.var_domain, None),
        ]
        for i, (lab, var, mask) in enumerate(fields):
            ttk.Label(frm_setup, text=lab).grid(
                row=i, column=0, sticky="e", padx=5, pady=4
            )
            ttk.Entry(frm_setup, textvariable=var, width=44, show=mask).grid(
                row=i, column=1, sticky="we", padx=5, pady=4
            )
        frm_setup.columnconfigure(1, weight=1)

        # Aktionen
        frm_actions = ttk.Frame(self)
        frm_actions.pack(fill="x", padx=10, pady=8)
        ttk.Button(frm_actions, text="NAS Setup", command=self.on_setup).pack(
            side="left", padx=5
        )
        ttk.Button(frm_actions, text="NAS Health", command=self.on_health).pack(
            side="left", padx=5
        )

        # Manueller Upload
        frm_upload = ttk.LabelFrame(self, text="Manueller Upload")
        frm_upload.pack(fill="x", padx=10, pady=8)
        self.var_run_id = tk.StringVar(value="")
        ttk.Label(frm_upload, text="run_id:").grid(
            row=0, column=0, sticky="e", padx=5, pady=4
        )
        ttk.Entry(frm_upload, textvariable=self.var_run_id, width=30).grid(
            row=0, column=1, sticky="w", padx=5, pady=4
        )
        ttk.Button(frm_upload, text="enqueue Upload", command=self.on_upload).grid(
            row=0, column=2, padx=5, pady=4
        )

        # Ausgabe
        frm_out = ttk.LabelFrame(self, text="Server Response")
        frm_out.pack(fill="both", expand=True, padx=10, pady=8)
        self.txt = tk.Text(frm_out, height=10)
        self.txt.pack(fill="both", expand=True, padx=5, pady=5)

    def adapter(self) -> NASApiAdapter:
        return NASApiAdapter(self.var_base.get().strip(), self.var_key.get().strip())

    def on_setup(self):
        try:
            res = self.adapter().setup(
                host=self.var_host.get().strip(),
                share=self.var_share.get().strip(),
                username=self.var_user.get().strip(),
                password=self.var_pass.get(),
                base_subdir=self.var_subdir.get().strip(),
                retention_days=int(self.var_ret.get().strip() or "14"),
                domain=self.var_domain.get().strip() or None,
            )
            self._show(res)
            messagebox.showinfo("Setup", "NAS (SMB) Setup abgeschlossen.")
        except requests.HTTPError as e:
            self._show_resp(e.response)
            messagebox.showerror("Fehler", f"HTTP {e.response.status_code}")
        except Exception as e:
            self._append(str(e))

    def on_health(self):
        try:
            res = self.adapter().health()
            self._show(res)
        except requests.HTTPError as e:
            self._show_resp(e.response)
        except Exception as e:
            self._append(str(e))

    def on_upload(self):
        rid = self.var_run_id.get().strip()
        if not rid:
            messagebox.showwarning("Notice", "Please enter run_id.")
            return
        try:
            res = self.adapter().upload_run(rid)
            self._show(res)
            messagebox.showinfo("Upload", "Upload enqueued (see logs on the Pi).")
        except requests.HTTPError as e:
            self._show_resp(e.response)
        except Exception as e:
            self._append(str(e))

    # Hilfen
    def _show(self, obj):
        self.txt.delete("1.0", "end")
        self.txt.insert("end", json.dumps(obj, indent=2, ensure_ascii=False))

    def _show_resp(self, resp):
        try:
            self._show(resp.json())
        except Exception:
            self._append(resp.text)

    def _append(self, text: str):
        self.txt.insert("end", text + "\n")
        self.txt.see("end")

    def _on_close(self):
        try:
            if self.winfo_exists():
                self.destroy()
        finally:
            if self._root_window is not None:
                try:
                    self._root_window.destroy()
                except tk.TclError:
                    pass


if __name__ == "__main__":
    NASSetupGUI().mainloop()
