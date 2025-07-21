import tkinter as tk
from tkinter import ttk

def build_folder_tree(app):
    # Frame to hold the tree and scrollbars
    tree_frame = tk.Frame(app.files_frame)
    tree_frame.pack(fill="both", expand=True)

    # Vertical and Horizontal Scrollbars
    vbar_tree = ttk.Scrollbar(tree_frame, orient="vertical")
    vbar_tree.pack(side="right", fill="y")

    hbar_tree = ttk.Scrollbar(tree_frame, orient="horizontal")
    hbar_tree.pack(side="bottom", fill="x")

    # Treeview for displaying folder structure
    app.tree = ttk.Treeview(
        tree_frame,
        columns=("filepath",),
        show="tree headings",
        yscrollcommand=vbar_tree.set,
        xscrollcommand=hbar_tree.set,
    )

    # Define column headers and layout
    app.tree.heading("#0", text="Name")
    app.tree.column("#0", width=450, anchor="w", stretch=False)
    app.tree.heading("filepath", text="File Path")
    app.tree.column("filepath", width=450, anchor="w", stretch=False)
    app.tree.pack(fill="both", expand=True)

    # Configure scrollbars to sync with treeview
    vbar_tree.config(command=app.tree.yview)
    hbar_tree.config(command=app.tree.xview)

    # Bind select event to handle node click
    app.tree.bind("<<TreeviewSelect>>", app._select_node)

    # Function to resize columns dynamically
    def resize_tree_columns(event):
        tree = event.widget
        total_width = tree.winfo_width()
        col_width = max(int(total_width / 2), 100)
        tree.column("#0", width=col_width, stretch=False)
        tree.column("filepath", width=col_width, stretch=False)

    # Bind the resize event to adjust column width
    app.tree.bind("<Configure>", resize_tree_columns)

    # Function to load folder structure into the tree (example: recursively add files/folders)
    def populate_tree(directory):
        for dirpath, dirnames, filenames in os.walk(directory):
            parent = app.tree.insert("", "end", text=dirpath, values=(dirpath,))
            for filename in filenames:
                app.tree.insert(parent, "end", text=filename, values=(os.path.join(dirpath, filename),))

    # Call populate_tree when the folder path is known (Example: use a button to trigger this)
    # populate_tree("/your/directory/path")

    return app.tree  # Optionally return tree reference for further use
