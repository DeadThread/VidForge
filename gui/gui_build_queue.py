import tkinter as tk
from tkinter import ttk

def setup_queue_tree(app):
    """Setup the Queue tree and its functionalities."""

    # ─────────────── Queue tree inside app.frame_queue ────────────────
    tk.Label(app.frame_queue, text="Queue:").pack(anchor="w")
    queue_frame = tk.Frame(app.frame_queue)
    queue_frame.pack(fill="both", expand=True)

    app.queue_tree = ttk.Treeview(queue_frame, columns=("original", "proposed"),
                                  show="headings", selectmode="extended")
    app.queue_tree.heading("original", text="Original Filename")
    app.queue_tree.heading("proposed", text="Proposed Filename")
    app.queue_tree.column("original", width=450, anchor="w", stretch=False)
    app.queue_tree.column("proposed", width=450, anchor="w", stretch=False)

    vbar_q = ttk.Scrollbar(queue_frame, orient="vertical", command=app.queue_tree.yview)
    hbar_q = ttk.Scrollbar(queue_frame, orient="horizontal", command=app.queue_tree.xview)

    app.queue_tree.configure(yscrollcommand=vbar_q.set, xscrollcommand=hbar_q.set)

    app.queue_tree.grid(row=0, column=0, sticky="nsew")
    vbar_q.grid(row=0, column=1, sticky="ns")
    hbar_q.grid(row=1, column=0, sticky="ew")

    queue_frame.grid_rowconfigure(0, weight=1)
    queue_frame.grid_columnconfigure(0, weight=1)

    def resize_queue_columns(event):
        tree = event.widget
        total_width = tree.winfo_width()

        # Let's split evenly between the two columns:
        col_width = max(int(total_width / 2), 100)  # minimum 100 px each

        tree.column("original", width=col_width, stretch=False)
        tree.column("proposed", width=col_width, stretch=False)

    app.queue_tree.bind("<Configure>", resize_queue_columns)
