#!/usr/bin/env python
# VidForge – 2025‑06‑25 queue‑aware Photoshop (non‑blocking) edition
# (adds TimedRotatingFileHandler + 30‑day cleanup)

import os, re, shutil, time, subprocess, threading, tkinter as tk
from tkinter import filedialog, ttk, messagebox
from datetime import datetime, timedelta
import logging
from logging.handlers import TimedRotatingFileHandler

# ───── constants ─────────────────────────────────────────────────────
VIDEO_EXT = (".mp4",".mkv",".mov",".m4v",".avi",".flv",".webm",
             ".ts",".mpg",".mpeg")
ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "assets","TagForge.ico")
PS_EXE    = r"C:\Program Files\Adobe\Adobe Photoshop 2025\Photoshop.exe"

STATE_ABBR = {"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
              "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
              "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
              "VA","WA","WV","WI","WY"}
RES_RE      = re.compile(r"(2160|1440|1080|720|480|360|240)p?", re.I)
FORMAT_LIST = ["2160p","1080p","720p","480p","LQ",""]

# ───── logging setup ────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("vidforge")
# Appflow logger (INFO only)
appflow = logging.getLogger("vidforge.app")
appflow.setLevel(logging.INFO)
afh = TimedRotatingFileHandler(
        os.path.join(LOG_DIR, "appflow.log"),
        when="midnight", interval=1, backupCount=30, encoding="utf-8")
afh.setLevel(logging.INFO)
afh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
appflow.addHandler(afh)
logger.setLevel(logging.DEBUG)

# console output
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
logger.addHandler(ch)

# daily rotating file
fh = TimedRotatingFileHandler(
        os.path.join(LOG_DIR, "vidforge.log"),
        when="midnight", interval=1, backupCount=30, encoding="utf-8")
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(fh)

# remove >30‑day extras (if user changed backupCount)
cutoff = datetime.now() - timedelta(days=30)
for f in os.listdir(LOG_DIR):
    p = os.path.join(LOG_DIR, f)
    if os.path.isfile(p) and os.path.getmtime(p) < cutoff.timestamp():
        try:
            os.remove(p)
            logger.debug("Deleted old log file %s", f)
        except Exception as e:
            logger.error("Cannot delete log %s: %s", f, e)

# ──── token helpers ─────────────────────────────────────────────────
TOKEN_SPLIT_RE = re.compile(r"[^\w']+")
STATE_SET = {s.lower() for s in STATE_ABBR}

def split_tokens(text:str)->list[str]:
    tok=[t for t in TOKEN_SPLIT_RE.split(text.lower()) if t]
    logger.debug("split_tokens(%s) -> %s", text, tok)
    return tok

def find_state(tok:list[str]):
    for i,t in enumerate(tok):
        if t in STATE_SET:
            logger.debug("find_state -> %s @ %d", t.upper(), i)
            return i, t.upper()
    logger.debug("find_state -> none")
    return None

# ──── simple helpers ────────────────────────────────────────────────
def normalize_name(s:str)->str:
    n=re.sub(r"[^\w]","",s.lower())
    logger.debug("normalize_name(%s) -> %s", s, n)
    return n

def extract_date(text:str)->str:
    for pat,fmt in ((re.compile(r"(\d{4})[-./](\d{2})[-./](\d{2})"),"%Y-%m-%d"),
                    (re.compile(r"(\d{2})[-./](\d{2})[-./](\d{4})"),"%m-%d-%Y"),
                    (re.compile(r"(\d{2})[-./](\d{2})[-./](\d{2})"),"%y-%m-%d")):
        m=pat.search(text)
        if m:
            try:
                out=datetime.strptime("-".join(m.groups()),fmt).strftime("%Y-%m-%d")
                logger.debug("extract_date(%s) -> %s", text, out)
                return out
            except Exception as e:
                logger.debug("extract_date parse error: %s", e)
    logger.debug("extract_date(%s) -> ''", text)
    return ""

CITY_STATE_RE=re.compile(
    rf"""(?P<city>[A-Za-z.\'-]+?)\s*[,\.\- ]+\s*(?P<st>{'|'.join(STATE_ABBR)})\b""",
    re.I|re.X)

# ───── venue matcher ────────────────────────────────────────────────
def extract_venue(base:str, venues:dict[str,str])->str:
    def chk(c):
        n=normalize_name(c)
        return venues.get(n, c.title() if c else "")
    parts=[p.strip() for p in base.split(" - ")]
    if len(parts)>=3:
        cand=parts[2]; res=chk(cand)
        if res:
            logger.debug("venue dash‑slot %s -> %s", cand, res)
            return res
    toks=re.split(r"[.\s_\-]+",base)
    for w in range(4,0,-1):
        for i in range(len(toks)-w+1):
            chunk=" ".join(toks[i:i+w])
            if normalize_name(chunk) in venues:
                logger.debug("venue window %s", chunk)
                return venues[normalize_name(chunk)]
    normb=normalize_name(base)
    for k,v in venues.items():
        if k in normb:
            logger.debug("venue substring %s", v)
            return v
    logger.debug("venue none")
    return ""

# ───── core parse ───────────────────────────────────────────────────
def infer_from_name(fname, artists, cities, venues):
    base=os.path.splitext(fname)[0]; norm=normalize_name(base)
    info={"artist":"","date":"","venue":"","city":"","format":"","additional":""}

    info["artist"]=next((v for k,v in artists.items() if k in norm),"") or \
                   re.split(r"[._\-\s]",base)[0].title()
    info["date"]=extract_date(base)
    info["format"]="2160p" if re.search(r"\b4k\b",base,re.I) else \
                   (m:=RES_RE.search(base)) and f"{m.group(1)}p" or ""
    info["venue"]=extract_venue(base,venues)

    purified=base
    parts=[p.strip() for p in base.split(" - ")]
    if len(parts)>=3 and normalize_name(parts[2])==normalize_name(info["venue"]):
        purified=" - ".join(parts[:2]+parts[3:])
    norm_pur=normalize_name(purified)

    key=next((k for k in cities if k in norm_pur),None)
    if key:
        cname=cities[key].rstrip(", ")
        hit=CITY_STATE_RE.search(purified)
        if hit:
            st=hit.group("st").upper()
            if not cname.upper().endswith(st): cname=f"{cname}, {st}"
        info["city"]=cname
    else:
        toks=split_tokens(purified)
        st_hit=find_state(toks[::-1])
        if st_hit and st_hit[0]<len(toks)-1:
            idx_r,st=st_hit; idx=len(toks)-1-idx_r
            raw=toks[idx-1] if idx else ""
            if raw:
                info["city"]=f"{cities.get(raw,raw.title())}, {st}"
    logger.debug("infer_from_name(%s) -> %s", fname, info)
    return info

def touch(path, ymd):
    try:
        ts=time.mktime(datetime.strptime(ymd,"%Y-%m-%d").timetuple())
        os.utime(path,(ts,ts))
        logger.debug("touch %s -> %s", path, ymd)
    except Exception as e:
        logger.error("touch error %s: %s", path, e)

# ───── GUI class (unchanged except _log now forwards to logger) ──────
class VideoTagger(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("VidForge"); self.geometry("1600x900")
        try:self.iconbitmap(ICON_PATH)
        except:print("[DEBUG] icon missing")

        self.root_dir=tk.StringVar(); self.current_fp=None
        self.queue=[]; self.meta={}
        self.hist={"additional":set()}

        base=os.path.dirname(os.path.abspath(__file__))
        self.assets=os.path.join(base,"assets")
        print("[DEBUG] Assets folder:",self.assets if os.path.isdir(self.assets) else "NONE")

        self.artist=self._load_names("Artists.txt")
        self.city  =self._load_names("Cities.txt")
        self.venue =self._load_names("Venues.txt")

        self._build_gui()

    # txt helpers
    def _load_names(self,f):
        d={}
        if self.assets and os.path.isfile(os.path.join(self.assets,f)):
            with open(os.path.join(self.assets,f),encoding="utf-8") as fl:
                for ln in fl:
                    ln=ln.strip()
                    if ln:d[normalize_name(ln)]=ln
        print(f"[DEBUG] loaded {len(d)} {f}")
        return d

    def _append_if_new(self,cat,name):
        if not (name and self.assets):return
        d,f={"artist":(self.artist,"Artists.txt"),
             "venue":(self.venue,"Venues.txt"),
             "city": (self.city ,"Cities.txt")}[cat]
        k=normalize_name(name)
        if k in d:return
        d[k]=name
        try:
            with open(os.path.join(self.assets,f),"a",encoding="utf-8") as fl:
                fl.write(name+"\n")
            self._log(f"Added new {cat}: {name}")
            print(f"[DEBUG] new {cat} '{name}' appended")
        except Exception as e:
            self._log(f"{f} write error: {e}")

    # GUI build
    def _build_gui(self):
        top=tk.Frame(self,pady=4); top.pack(fill="x")
        tk.Label(top,text="Root Folder:").pack(side="left")
        tk.Entry(top,textvariable=self.root_dir,width=80,state="readonly")\
            .pack(side="left",fill="x",expand=True)
        ttk.Button(top,text="Browse",command=self._browse).pack(side="left",padx=4)
        ttk.Button(top,text="Refresh",command=self._populate_tree).pack(side="left",padx=4)

        main=ttk.PanedWindow(self,orient="horizontal"); main.pack(fill="both",expand=True)
        left=tk.Frame(main); main.add(left,weight=3)
        vpan=ttk.PanedWindow(left,orient="vertical"); vpan.pack(fill="both",expand=True)

        # metadata frame -------------------------------------------------
        meta=tk.Frame(vpan); vpan.add(meta,weight=3)
        def row(lbl,var,r):
            tk.Label(meta,text=lbl).grid(row=r,column=0,sticky="w")
            cb=ttk.Combobox(meta,textvariable=var,width=34)
            cb.grid(row=r,column=1,sticky="w",padx=4)
            return cb
        self.v_artist=tk.StringVar(); self.cb_artist=row("Artist:",self.v_artist,0)
        tk.Label(meta,text="Format:").grid(row=0,column=2,sticky="w")
        self.v_format=tk.StringVar(value="1080p")
        ttk.Combobox(meta,textvariable=self.v_format,values=FORMAT_LIST,width=12)\
            .grid(row=0,column=3,sticky="w")
        self.v_venue=tk.StringVar(); self.cb_venue=row("Venue:",self.v_venue,1)
        self.v_city =tk.StringVar(); self.cb_city =row("City:", self.v_city,2)
        self.v_add  =tk.StringVar(); self.cb_add  =row("Additional:",self.v_add,3)
        tk.Label(meta,text="Date:").grid(row=1,column=2,sticky="w")
        dt=tk.Frame(meta); dt.grid(row=1,column=3,sticky="w")
        yrs=[str(y) for y in range(datetime.now().year,1999,-1)]
        months=[f"{m:02d}" for m in range(1,13)]
        days  =[f"{d:02d}" for d in range(1,32)]
        self.v_year,self.v_month,self.v_day=tk.StringVar(),tk.StringVar(),tk.StringVar()
        ttk.Combobox(dt,textvariable=self.v_year ,values=yrs ,width=6).grid(row=0,column=0)
        ttk.Combobox(dt,textvariable=self.v_month,values=months,width=4).grid(row=0,column=1)
        ttk.Combobox(dt,textvariable=self.v_day  ,values=days  ,width=4).grid(row=0,column=2)

        # files tree -----------------------------------------------------
        files=tk.Frame(vpan); vpan.add(files,weight=6)
        files.columnconfigure(0,weight=1); files.rowconfigure(1,weight=1)
        tk.Label(files,text="Video Files:").grid(row=0,column=0,sticky="w")
        self.tree=ttk.Treeview(files,show="tree",columns=("full",))
        self.tree.column("full",width=0,stretch=False)
        self.tree.grid(row=1,column=0,sticky="nsew")
        ttk.Scrollbar(files,orient="vertical",command=self.tree.yview)\
            .grid(row=1,column=1,sticky="ns")
        ttk.Scrollbar(files,orient="horizontal",command=self.tree.xview)\
            .grid(row=2,column=0,sticky="ew")
        self.tree.configure(yscroll=self.tree.yview,xscroll=self.tree.xview)
        self.tree.bind("<<TreeviewSelect>>",self._select_node)

        btn=tk.Frame(files); btn.grid(row=3,column=0,columnspan=2,sticky="w")
        ttk.Button(btn,text="Save Selected File",command=self._save_current)\
            .pack(side="left",padx=4)
        ttk.Button(btn,text="Remove Selected",command=self._remove_sel)\
            .pack(side="left",padx=4)
        ttk.Button(btn,text="Process Queue",command=self._process_queue)\
            .pack(side="left",padx=4)
        ttk.Button(btn,text="Clear Fields",command=self._clear_fields)\
            .pack(side="left",padx=4)

        queue=tk.Frame(vpan); vpan.add(queue,weight=2)
        tk.Label(queue,text="Files in Queue:").pack(anchor="w")
        self.lb_queue=tk.Listbox(queue); self.lb_queue.pack(fill="both",expand=True)

        # log pane -------------------------------------------------------
        right=tk.Frame(main); main.add(right,weight=2)
        tk.Label(right,text="Log:").pack(anchor="w")
        self.log=tk.Text(right,wrap="none"); self.log.pack(fill="both",expand=True)
        ttk.Scrollbar(right,orient="vertical",command=self.log.yview)\
            .pack(side="right",fill="y")
        ttk.Scrollbar(right,orient="horizontal",command=self.log.xview)\
            .pack(side="bottom",fill="x")
        self._refresh_dd()
        self.protocol("WM_DELETE_WINDOW",self._on_close)

    # ── tree helpers ---------------------------------------------------
    def _browse(self):
        d=filedialog.askdirectory()
        if d:self.root_dir.set(d); self._populate_tree()

    def _populate_tree(self):
        root=self.root_dir.get()
        if not root or not os.path.isdir(root):
            messagebox.showerror("Error","Select valid root"); return
        self.tree.delete(*self.tree.get_children())
        self._log(f"Scanning {root}")
        self._add_recursive("",root)

    def _add_recursive(self,parent,path):
        try:items=sorted(os.listdir(path))
        except:items=[]
        for itm in items:
            full=os.path.join(path,itm)
            if os.path.isdir(full):
                node=self.tree.insert(parent,"end",text=itm,open=False,
                                      values=(full,))
                self._add_recursive(node,full)
            elif os.path.isfile(full) and itm.lower().endswith(VIDEO_EXT):
                self.tree.insert(parent,"end",text=itm,values=(full,))

    # ── selection ------------------------------------------------------
    def _select_node(self,_=None):
        sel=self.tree.selection()
        if not sel:return
        fp=self.tree.item(sel[0],"values")[0]
        if not os.path.isfile(fp):return
        self.current_fp=fp
        meta=infer_from_name(os.path.basename(fp),
                             self.artist,self.city,self.venue)
        self.v_artist.set(meta["artist"])
        self.v_format.set(meta["format"] or "1080p")
        self.v_venue .set(meta["venue"])
        self.v_city  .set(meta["city"])
        self.v_add   .set(meta["additional"])
        if meta["date"]:
            y,m,d=meta["date"].split("-")
            self.v_year.set(y); self.v_month.set(m); self.v_day.set(d)
        else:
            self.v_year.set(""); self.v_month.set(""); self.v_day.set("")

    # ── queue ops ------------------------------------------------------
    def _save_current(self):
        if not self.current_fp:
            messagebox.showinfo("No file","Select a video first."); return
        md=self._gather_meta()
        self.meta[self.current_fp]=md
        if self.current_fp not in self.queue:
            self.queue.append(self.current_fp)
            self.lb_queue.insert("end",self.current_fp)
        self._log(f"Saved metadata: {self.current_fp}")

    def _remove_sel(self):
        if not self.lb_queue.curselection():return
        i=self.lb_queue.curselection()[0]; fp=self.lb_queue.get(i)
        self.lb_queue.delete(i); self.queue.remove(fp); self.meta.pop(fp,None)

    def _clear_fields(self):
        for v in (self.v_artist,self.v_format,self.v_venue,self.v_city,
                  self.v_add,self.v_year,self.v_month,self.v_day):v.set("")
        self.current_fp=None

    # ── processing thread ---------------------------------------------
    def _process_queue(self):
        if not self.queue:
            messagebox.showinfo("Empty","Queue is empty."); return
        if not self.root_dir.get():
            messagebox.showerror("No root","Pick a root folder."); return
        self._log("Starting processing …")
        threading.Thread(target=self._worker,daemon=True).start()

    def _worker(self):
        root=self.root_dir.get()
        while self.queue:
            src=self.queue.pop(0); self.lb_queue.delete(0)
            md=self.meta.pop(src,{})
            date=md.get("date") or extract_date(os.path.basename(src))
            if not date:
                self._log(f"Skip {src}: no date"); continue
            artist=md.get("artist") or "Unknown"; year=date[:4]
            base=" - ".join(x for x in (artist,date,md.get("venue"),
                                        md.get("city")) if x)
            tags=[f"[{md['format']}]" if md.get("format") else "",
                  f"[{md['additional']}]" if md.get("additional") else ""]
            base+=" "+ " ".join(t for t in tags if t)
            dest_dir=os.path.join(root,artist,year,base)
            os.makedirs(dest_dir,exist_ok=True)
            dest_fp=os.path.join(dest_dir,base+os.path.splitext(src)[1].lower())
            try:
                if os.path.abspath(src)!=os.path.abspath(dest_fp):
                    shutil.move(src,dest_fp); touch(dest_fp,date)
                    self._log(f"Moved: {src} → {dest_fp}")
                self._generate_poster(artist,md,dest_dir,len(self.queue)==0)
            except Exception as e:
                self._log(f"Error: {e}")
        self._log("Processing finished.")

    # ── photoshop ------------------------------------------------------
    def _generate_poster(self, artist, md, dest_dir, last_job):
        if not self.assets:
            return

        # ── locate template ──────────────────────────────────────────────
        tmpl_dir = os.path.join(self.assets, "Photoshop Templates")
        if not os.path.isdir(tmpl_dir):
            return

        norm = normalize_name(artist)

        # 1️⃣ artist‑specific
        template = next(
            (
                os.path.join(tmpl_dir, f)
                for f in os.listdir(tmpl_dir)
                if normalize_name(os.path.splitext(f)[0]).startswith(norm)
            ),
            None,
        )

        # 2️⃣ fallback → Generic.psd
        if template is None:
            generic = next(
                (
                    os.path.join(tmpl_dir, f)
                    for f in os.listdir(tmpl_dir)
                    if normalize_name(os.path.splitext(f)[0]) == "generic"
                ),
                None,
            )
            if generic:
                template = generic
                self._log("Using Generic.psd poster template")
            else:
                self._log(f"No template for {artist}; skipped.")
                return

        # ── path prep ────────────────────────────────────────────────────
        poster_png = os.path.join(dest_dir, "Poster.png").replace("\\", "/")
        poster_psd = os.path.join(dest_dir, "Poster.psd").replace("\\", "/")
        jsx_path   = os.path.join(dest_dir, "poster_gen.jsx")
        template   = template.replace("\\", "/")

        # ── build JSX ────────────────────────────────────────────────────
        # include ARTIST as a replace‑able field
        esc_artist = artist.replace('"', r'\"')
        jsx = f'''// VidForge JSX (auto‑generated)
    var d = app.open(new File("{template}"));
    var M = {{
        "Artist":"{esc_artist}",
        "Date":"{md.get('date', '')}",
        "Venue":"{md.get('venue', '')}",
        "City":"{md.get('city', '')}"
    }};
    for (var k in M) {{
        try {{
            var l = d.artLayers.getByName(k);
            if (l.kind == LayerKind.TEXT) l.textItem.contents = M[k];
        }} catch(e) {{ /* layer missing → ignore */ }}
    }}
    d.saveAs(new File("{poster_psd}"));
    var o = new PNGSaveOptions();
    d.saveAs(new File("{poster_png}"), o, true);
    d.close(SaveOptions.DONOTSAVECHANGES);
    '''

        # ── run Photoshop & monitor output ───────────────────────────────
        try:
            with open(jsx_path, "w", encoding="utf-8") as f:
                f.write(jsx)
            self._log(f"JSX created: {jsx_path}")

            subprocess.Popen([PS_EXE, "-r", jsx_path],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)

            start = time.time()
            while time.time() - start < 180 and not os.path.isfile(poster_png):
                time.sleep(2)

            if os.path.isfile(poster_png):
                self._log(f"Poster PNG created: {poster_png}")
                self._log(f"Poster PSD created: {poster_psd}")
            else:
                self._log("Poster generation timeout (180 s)")

            try:
                os.remove(jsx_path)
                self._log("JSX deleted.")
            except Exception:
                pass

            if last_job:
                self._close_photoshop()

        except Exception as e:
            self._log(f"Photoshop error: {e}")

    def _close_photoshop(self):
        try:
            subprocess.run(["taskkill","/F","/IM","Photoshop.exe"],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                           check=True)
            self._log("Photoshop closed.")
        except Exception as e:
            self._log(f"Could not close Photoshop: {e}")

    # ── misc -----------------------------------------------------------
    def _gather_meta(self):
        y,m,d=self.v_year.get(),self.v_month.get(),self.v_day.get()
        date=""
        if y and m and d:
            try:date=f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
            except:pass
        return {"artist":self.v_artist.get().strip(),
                "venue": self.v_venue.get().strip(),
                "city":  self.v_city.get().strip(),
                "format":self.v_format.get().strip(),
                "additional":self.v_add.get().strip(),
                "date":date}

    def _log(self, msg):
        t = f"[{datetime.now():%H:%M:%S}] {msg}"
        self.log.insert("end", t + "\n")
        self.log.see("end")
        print(t)
        appflow.info(msg)   # <-- Use appflow here to log to appflow.log

    def _refresh_dd(self):
        for cb,vals in ((self.cb_artist,self.artist.values()),
                        (self.cb_venue ,self.venue .values()),
                        (self.cb_city  ,self.city  .values()),
                        (self.cb_add   ,self.hist["additional"])):
            cb["values"]=sorted(vals)

    def _on_close(self):
        try:self._close_photoshop()
        except:pass
        self.destroy()

# ── run ───────────────────────────────────────────────────────────────
if __name__=="__main__":
    VideoTagger().mainloop()
