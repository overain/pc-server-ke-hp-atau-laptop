import os, re, shutil, socket, zipfile
from urllib.parse import quote
from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel
import auth

ROOT = Path(__file__).parent
STORAGE = ROOT / "storage"
STORAGE.mkdir(exist_ok=True)
(STORAGE / "_shared").mkdir(exist_ok=True)
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")
FNAME_RE = re.compile(r"^[\w .-]{1,32}$")
SENSITIVE = {(ROOT / "users.json").resolve(), (ROOT / "folders.json").resolve()}

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

def current_user(request: Request):
    u = auth.get_session(request.cookies.get("sid", ""))
    if not u: raise HTTPException(401, "Belum login")
    return u

def writable(space):
    if space.startswith("f:"):
        f = auth.folders().get(space[2:])
        if f and f.get("readonly"): raise HTTPException(403, "Folder ini baca-saja")

@app.get("/api/spaces")
def spaces(user=Depends(current_user)):
    out = [{"id": "me", "name": "Folder saya"}, {"id": "shared", "name": "Folder bersama"}]
    for k, f in auth.folders().items():
        if auth.can_access(user, f): out.append({"id": "f:" + k, "name": "💻 " + k + (" (baca-saja)" if f.get("readonly") else "")})
    return out

def resolve(user, space, rel):
    if space.startswith("f:"):
        f = auth.folders().get(space[2:])
        if not f or not auth.can_access(user, f): raise HTTPException(403, "Tidak ada akses")
        base = Path(f["path"])
        if not base.is_dir(): raise HTTPException(404, "Folder PC tidak ditemukan")
    elif space == "shared": base = STORAGE / "_shared"
    elif space == "me":
        if not NAME_RE.match(user): raise HTTPException(400, "Nama user tidak valid")
        base = STORAGE / user
    else: raise HTTPException(400, "Space tidak valid")
    if not space.startswith("f:"): base.mkdir(exist_ok=True)
    base = base.resolve()
    p = (base / rel.lstrip("/\\")).resolve()
    if p != base and base not in p.parents:
        raise HTTPException(400, "Path tidak valid")
    if p in SENSITIVE: raise HTTPException(403, "Dilarang")
    return base, p

class Login(BaseModel):
    username: str
    password: str

@app.post("/api/login")
def login(b: Login, request: Request, response: Response):
    ip = request.client.host
    if auth.too_many(ip): raise HTTPException(429, "Terlalu banyak percobaan, tunggu 5 menit")
    if not auth.verify(b.username, b.password):
        auth.fail(ip); raise HTTPException(401, "Username/password salah")
    auth.ok(ip)
    response.set_cookie("sid", auth.new_session(b.username), httponly=True, samesite="strict", max_age=auth.TTL)
    return {"user": b.username}

@app.post("/api/logout")
def logout(request: Request, response: Response):
    auth.drop_session(request.cookies.get("sid", "")); response.delete_cookie("sid"); return {}

@app.get("/api/me")
def me(user=Depends(current_user)):
    return {"user": user, "admin": auth.list_users().get(user, False)}

@app.get("/api/list")
def list_dir(space: str, path: str = "", user=Depends(current_user)):
    base, p = resolve(user, space, path)
    if not p.is_dir(): raise HTTPException(404, "Folder tidak ada")
    items = []
    for e in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        try: st = e.stat()
        except OSError: continue
        if e.resolve() in SENSITIVE: continue
        items.append({"name": e.name, "dir": e.is_dir(), "size": 0 if e.is_dir() else st.st_size, "mtime": st.st_mtime})
    return {"path": str(p.relative_to(base)).replace("\\", "/").replace(".", "") if p != base else "", "items": items}

@app.post("/api/upload")
async def upload(space: str, path: str = "", files: list[UploadFile] = File(...), user=Depends(current_user)):
    writable(space)
    _, d = resolve(user, space, path)
    if not d.is_dir(): raise HTTPException(404, "Folder tidak ada")
    for f in files:
        name = Path(f.filename.replace("\\", "/")).name
        if not name: continue
        tgt = d / name
        if space.startswith("f:") and tgt.exists(): raise HTTPException(409, "File sudah ada: " + name)
        with open(tgt, "wb") as out:
            shutil.copyfileobj(f.file, out, 1024 * 1024)
    return {"ok": True}

@app.get("/api/download")
def download(space: str, path: str, user=Depends(current_user)):
    _, p = resolve(user, space, path)
    if not p.is_file(): raise HTTPException(404, "File tidak ada")
    return FileResponse(p, filename=p.name)

class _Sink:
    def __init__(self): self.buf = []; self.pos = 0
    def write(self, b): self.buf.append(bytes(b)); self.pos += len(b); return len(b)
    def tell(self): return self.pos
    def flush(self): pass
    def drain(self): d = b"".join(self.buf); self.buf = []; return d

def zip_stream(folder: Path, root_name: str):
    sink = _Sink()
    zf = zipfile.ZipFile(sink, "w", zipfile.ZIP_STORED, allowZip64=True)
    zf.writestr(root_name + "/", b"")
    for cur, dirs, files in os.walk(folder, followlinks=False):
        cur = Path(cur)
        dirs[:] = [d for d in dirs if not (cur / d).is_symlink()]
        rel = cur.relative_to(folder).as_posix()
        arc_dir = root_name if rel == "." else root_name + "/" + rel
        if not dirs and not files and rel != ".": zf.writestr(arc_dir + "/", b"")
        for fn in files:
            fp = cur / fn
            if fp.is_symlink() or fp.resolve() in SENSITIVE: continue
            try: src = open(fp, "rb")
            except OSError: continue
            with src:
                zi = zipfile.ZipInfo.from_file(fp, arc_dir + "/" + fn)
                zi.compress_type = zipfile.ZIP_STORED
                with zf.open(zi, "w", force_zip64=True) as dst:
                    while True:
                        c = src.read(1024 * 1024)
                        if not c: break
                        dst.write(c)
                        yield sink.drain()
        yield sink.drain()
    zf.close()
    yield sink.drain()

@app.get("/api/download-folder")
def download_folder(space: str, path: str = "", user=Depends(current_user)):
    base, p = resolve(user, space, path)
    if not p.is_dir(): raise HTTPException(404, "Folder tidak ada")
    name = p.name or (space[2:] if space.startswith("f:") else user if space == "me" else "bersama")
    name = re.sub(r'[\\/:*?"<>|]', "_", name) or "folder"
    return StreamingResponse(zip_stream(p, name), media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(name + ".zip")})

class PathBody(BaseModel):
    space: str
    path: str
    name: str = ""

@app.post("/api/mkdir")
def mkdir(b: PathBody, user=Depends(current_user)):
    writable(b.space)
    _, p = resolve(user, b.space, b.path + "/" + Path(b.name).name)
    p.mkdir(exist_ok=True); return {"ok": True}

@app.post("/api/delete")
def delete(b: PathBody, user=Depends(current_user)):
    writable(b.space)
    base, p = resolve(user, b.space, b.path)
    if p == base or not p.exists(): raise HTTPException(404, "Tidak ada")
    shutil.rmtree(p) if p.is_dir() else p.unlink()
    return {"ok": True}

@app.post("/api/rename")
def rename(b: PathBody, user=Depends(current_user)):
    writable(b.space)
    base, p = resolve(user, b.space, b.path)
    if p == base or not p.exists(): raise HTTPException(404, "Tidak ada")
    new = p.with_name(Path(b.name).name)
    if new.exists(): raise HTTPException(409, "Nama sudah dipakai")
    p.rename(new); return {"ok": True}

# ---------- ADMIN ----------
def admin_only(user=Depends(current_user)):
    if not auth.list_users().get(user): raise HTTPException(403, "Khusus admin")
    return user

@app.get("/api/admin/browse")
def browse(path: str = "", user=Depends(admin_only)):
    if not path:
        if os.name == "nt":
            return {"path": "", "parent": None, "dirs": [f"{c}:\\" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{c}:\\")]}
        path = "/"
    p = Path(path)
    if not p.is_dir(): raise HTTPException(404, "Folder tidak ada")
    dirs = []
    try:
        for e in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            try:
                if e.is_dir(): dirs.append(str(e))
            except OSError: pass
    except PermissionError: raise HTTPException(403, "Tidak boleh dibuka oleh Windows")
    parent = str(p.parent) if p.parent != p else ("" if os.name == "nt" else None)
    return {"path": str(p), "parent": parent, "dirs": dirs}

@app.get("/api/admin/folders")
def a_folders(user=Depends(admin_only)): return auth.folders()

class FolderBody(BaseModel):
    name: str
    path: str = ""
    users: list[str] = ["admin"]
    readonly: bool = False

@app.post("/api/admin/folders")
def a_folder_add(b: FolderBody, user=Depends(admin_only)):
    if not FNAME_RE.match(b.name): raise HTTPException(400, "Nama folder: huruf/angka/spasi/-/_/., maks 32")
    if not os.path.isdir(b.path): raise HTTPException(400, "Folder tidak ditemukan di PC")
    known = set(auth.list_users())
    us = ["*"] if "*" in b.users else [u for u in b.users if u in known] or ["admin"]
    auth.add_folder(b.name, b.path, us, b.readonly); return {"ok": True}

@app.post("/api/admin/folders/delete")
def a_folder_del(b: FolderBody, user=Depends(admin_only)):
    auth.del_folder(b.name); return {"ok": True}

@app.get("/api/admin/users")
def a_users(user=Depends(admin_only)): return auth.list_users()

class UserBody(BaseModel):
    name: str
    password: str = ""
    admin: bool = False

@app.post("/api/admin/users")
def a_user_add(b: UserBody, user=Depends(admin_only)):
    if not NAME_RE.match(b.name): raise HTTPException(400, "Username: huruf/angka/_/-/., maks 32")
    if len(b.password) < 6: raise HTTPException(400, "Password minimal 6 karakter")
    auth.add_user(b.name, b.password, b.admin); return {"ok": True}

@app.post("/api/admin/users/delete")
def a_user_del(b: UserBody, user=Depends(admin_only)):
    if b.name == user: raise HTTPException(400, "Tidak bisa menghapus diri sendiri")
    auth.delete_user(b.name)
    for t, (n, _) in list(auth.SESSIONS.items()):
        if n == b.name: auth.SESSIONS.pop(t, None)
    return {"ok": True}

@app.get("/")
def index():
    return HTMLResponse((ROOT / "static" / "index.html").read_text(encoding="utf-8"))

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.connect(("10.255.255.255", 1)); return s.getsockname()[0]
    except Exception: return "127.0.0.1"
    finally: s.close()

if __name__ == "__main__":
    import uvicorn
    port = 8000
    print(f"\n  Buka dari laptop:  http://rain:{port}  (atau http://{lan_ip()}:{port})\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
