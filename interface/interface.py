import tkinter as tk
from tkinter import scrolledtext

root = tk.Tk()
root.title("Interface - Skeleton")
root.geometry("700x400")
root.minsize(500, 300)

# Disposición
root.grid_columnconfigure(1, weight=1)  
root.grid_rowconfigure(0, weight=1)

# Etiqueta "Dialogue" 
label_dialog = tk.Label(root, text="Dialogue", font=("Segoe UI", 10, "bold"))
label_dialog.grid(row=0, column=0, padx=(10,4), pady=10, sticky="n")

# Recuadro grande para el Dialogo
display = scrolledtext.ScrolledText(root, wrap=tk.WORD, state='disabled', font=("Segoe UI", 10), width=50, height=15)
display.grid(row=0, column=1, sticky="nsew", padx=(0,6), pady=10)

# Botón "Send file" 
btn_file = tk.Button(root, text="Send file", width=14)
btn_file.grid(row=0, column=2, padx=(4,10), pady=10, sticky="n")

# Etiqueta "Text"
label_text = tk.Label(root, text="Text", font=("Segoe UI", 10, "bold"))
label_text.grid(row=1, column=0, padx=(10,4), pady=(0,10), sticky="s")

# Campo de entrada para el texto
entry = tk.Entry(root, font=("Segoe UI", 11))
entry.grid(row=1, column=1, sticky="ew", padx=(0,6), pady=(0,10))

# Botón flecha ➤ para enviar texto
btn_send = tk.Button(root, text="➤", width=4, font=("Segoe UI", 12, "bold"))
btn_send.grid(row=1, column=2, padx=(4,10), pady=(0,10), sticky="s")

root.mainloop()
