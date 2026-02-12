"""Shared visual theme for SEVA desktop views.

The module centralizes ttk style tokens so all views can render a cohesive
modern look without carrying styling logic in each individual view class.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def apply_modern_theme(root: tk.Misc) -> None:
    """Apply a cohesive ttk + tk visual theme to the full application.

    Args:
        root: Root Tk object or any widget tied to the app Tcl interpreter.
    """
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    bg = "#f3f5f9"
    card_bg = "#ffffff"
    border = "#d9dfeb"
    primary = "#2457ff"
    text = "#1f2937"
    muted = "#64748b"

    root.option_add("*Font", "TkDefaultFont 10")
    root.configure(bg=bg)

    style.configure(".", background=bg, foreground=text)
    style.configure("TFrame", background=bg)
    style.configure("Card.TFrame", background=card_bg, relief="flat", borderwidth=1)
    style.configure("TLabelframe", background=bg, bordercolor=border, relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", foreground=text, background=bg, font=("TkDefaultFont", 10, "bold"))
    style.configure("TLabel", background=bg, foreground=text)
    style.configure("Subtle.TLabel", background=bg, foreground=muted)
    style.configure("Title.TLabel", background=bg, foreground=text, font=("TkDefaultFont", 14, "bold"))

    style.configure(
        "TButton",
        padding=(10, 6),
        background=card_bg,
        bordercolor=border,
        relief="flat",
    )
    style.map("TButton", background=[("active", "#edf2ff")])
    style.configure("Primary.TButton", background=primary, foreground="#ffffff", bordercolor=primary)
    style.map("Primary.TButton", background=[("active", "#1b45ce")])

    style.configure("TNotebook", background=bg, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(14, 8), background="#e7ecf6", foreground=text)
    style.map("TNotebook.Tab", background=[("selected", card_bg)], foreground=[("selected", text)])

    style.configure("Treeview", rowheight=28, fieldbackground=card_bg, background=card_bg, foreground=text)
    style.configure("Treeview.Heading", background="#e9eefb", foreground=text, relief="flat")
    style.map("Treeview", background=[("selected", "#d9e4ff")], foreground=[("selected", text)])

    style.configure("TEntry", fieldbackground="#ffffff", bordercolor=border)
    style.configure("TCombobox", fieldbackground="#ffffff", bordercolor=border)

