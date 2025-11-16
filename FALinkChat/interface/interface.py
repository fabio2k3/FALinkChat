import tkinter as tk
from tkinter import scrolledtext

root = tk.Tk()
root.title("Link-Chat — fsociety terminal")
root.geometry("700x400")
root.minsize(500, 300)

# Paleta de colores estilo Mr. Robot
BG = "#0b0f12"
TEXT = "#00ff41"
ACCENT = "#ff3131"
PANEL = "#111111"
ENTRY_BG = "#0d1f0d"
BTN_BG = "#1c1c1c"
MUTED = "#7f8c8d"

FONT_LABEL = ("Courier New", 10, "bold")
FONT_TEXT = ("Courier New", 10)
FONT_ENTRY = ("Courier New", 11)
FONT_BTN = ("Courier New", 12, "bold")

root.configure(bg=BG)

# Layout
root.grid_columnconfigure(1, weight=1)
root.grid_rowconfigure(0, weight=1)

# Etiqueta "Dialogue"
label_dialog = tk.Label(root, text="DIALOGUE", font=FONT_LABEL, fg=TEXT, bg=BG)
label_dialog.grid(row=0, column=0, padx=(10,4), pady=10, sticky="n")

# Recuadro grande para el diálogo 
display = scrolledtext.ScrolledText(
    root,
    wrap=tk.WORD,
    state='disabled',
    font=FONT_TEXT,
    width=50,
    height=15,
    bg=PANEL,
    fg=TEXT,
    insertbackground=TEXT,
    bd=0,
    relief="flat"
)
display.grid(row=0, column=1, sticky="nsew", padx=(0,6), pady=10)

# Botón "Connect" 
btn_connect = tk.Button(
    root,
    text="Connect",
    width=14,
    bg=BTN_BG,
    fg=TEXT,
    font=FONT_ENTRY,
    activebackground=ACCENT,
    activeforeground="black",
    bd=0
)
btn_connect.grid(row=0, column=3, padx=(4,10), pady=10, sticky="n")

# Botón "Send file"
btn_sendfile = tk.Button(
    root,
    text="Send file",
    width=14,
    bg=BTN_BG,
    fg=TEXT,
    font=FONT_ENTRY,
    activebackground=ACCENT,
    activeforeground="black",
    bd=0
)
btn_sendfile.grid(row=0, column=2, padx=(4,10), pady=10, sticky="n")

# Etiqueta "Text"
label_text = tk.Label(root, text="TEXT", font=FONT_LABEL, fg=TEXT, bg=BG)
label_text.grid(row=1, column=0, padx=(10,4), pady=(0,10), sticky="s")

# Campo de entrada para el texto
entry = tk.Entry(
    root,
    font=FONT_ENTRY,
    bg=ENTRY_BG,
    fg=TEXT,
    insertbackground=TEXT,
    bd=1,
    relief="solid"
)
entry.grid(row=1, column=1, sticky="ew", padx=(0,6), pady=(0,10))

# Botón flecha ➤ para enviar texto
btn_send = tk.Button(
    root,
    text="➤",
    width=4,
    font=FONT_BTN,
    bg=ACCENT,
    fg="black",
    activebackground="#ff5757",
    activeforeground="black",
    bd=0
)
btn_send.grid(row=1, column=2, padx=(4,10), pady=(0,10), sticky="s")

# Habilitar enviar con Enter 
def _on_entry_enter(event=None):
    try:
        btn_send.invoke()
    except Exception:
        pass
    return "break"

entry.bind("<Return>", _on_entry_enter)