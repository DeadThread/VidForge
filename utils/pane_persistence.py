def install_pane_persistence(pane, cfg, ini, section, option, log_func=None):
    def _do_restore():
        try:
            pos = cfg.getint(section, option, fallback=None)
            width = pane.winfo_width()
            if log_func:
                log_func(f"Pane width: {width}, restoring sash pos: {pos}")
            if pos is not None and width > 0:
                max_pos = max(0, width - 100)
                if pos > max_pos:
                    pos = max_pos
                pane.sashpos(0, pos)
                if log_func:
                    log_func(f"Restored sash position for {option}: {pos}")
        except Exception as e:
            if log_func:
                log_func(f"Failed restoring sash position for {option}: {e}")

    def delayed_restore():
        if pane.winfo_ismapped() and pane.winfo_width() > 100:
            _do_restore()
        else:
            pane.after(100, delayed_restore)

    pane.after_idle(delayed_restore)

    def on_configure(event):
        try:
            pos = cfg.getint(section, option, fallback=None)
            if pos is not None:
                pane.sashpos(0, pos)
                if log_func:
                    log_func(f"Restored sash position for {option}: {pos} (on configure)")
            pane.unbind("<Configure>", configure_id)
        except Exception:
            pass

    configure_id = pane.bind("<Configure>", on_configure)

    last = [pane.sashpos(0)]

    def _save(*_):
        try:
            cur = pane.sashpos(0)
            if cur == last[0]:
                return
            last[0] = cur
            if not cfg.has_section(section):
                cfg.add_section(section)
            cfg.set(section, option, str(cur))
            with open(ini, "w", encoding="utf-8") as f:
                cfg.write(f)
            if log_func:
                log_func(f"Saved sash position for {option}: {cur}")
        except Exception as e:
            if log_func:
                log_func(f"Failed saving sash position for {option}: {e}")

    pane.bind("<B1-Motion>", _save, add="+")
    pane.bind("<ButtonRelease-1>", _save, add="+")
