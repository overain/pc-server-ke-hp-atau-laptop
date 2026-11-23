import hashlib, hmac, json, os, secrets, time
from pathlib import Path

USERS_FILE = Path(__file__).parent / "users.json"

def _load():
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    return {}

def _save(d):
    USERS_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")

def _hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1).hex()

def add_user(name, password, admin=False):
    d = _load()
    salt = os.urandom(16)
    d[name] = {"salt": salt.hex(), "hash": _hash(password, salt), "admin": admin}
    _save(d)

def delete_user(name):
    d = _load(); d.pop(name, None); _save(d)

def list_users():
    return {k: v["admin"] for k, v in _load().items()}

def verify(name, password):
    u = _load().get(name)
    if not u:
        _hash(password, b"0" * 16)  # samakan waktu respons
        return False
    return hmac.compare_digest(u["hash"], _hash(password, bytes.fromhex(u["salt"])))

# --- sesi (di memori) ---
SESSIONS = {}
TTL = 60 * 60 * 24 * 7

def new_session(name):
    t = secrets.token_urlsafe(32)
    SESSIONS[t] = (name, time.time() + TTL)
    return t

def get_session(t):
    s = SESSIONS.get(t)
    if not s: return None
    if s[1] < time.time():
        SESSIONS.pop(t, None); return None
    return s[0]

def drop_session(t):
    SESSIONS.pop(t, None)

# --- batas percobaan login ---
FAILS = {}
def too_many(ip):
    n, t = FAILS.get(ip, (0, 0))
    return n >= 5 and time.time() - t < 300
def fail(ip):
    n, _ = FAILS.get(ip, (0, 0)); FAILS[ip] = (n + 1, time.time())
def ok(ip):
    FAILS.pop(ip, None)

# --- folder PC yang dibagikan ---
CFG = Path(__file__).parent / "folders.json"

def folders():
    return json.loads(CFG.read_text(encoding="utf-8")) if CFG.exists() else {}

def add_folder(name, path, users, readonly):
    d = folders(); d[name] = {"path": path, "users": users, "readonly": readonly}
    CFG.write_text(json.dumps(d, indent=2), encoding="utf-8")

def del_folder(name):
    d = folders(); d.pop(name, None); CFG.write_text(json.dumps(d, indent=2), encoding="utf-8")

def can_access(user, f):
    u = f["users"]
    return user in u or "*" in u or (u == ["admin"] and list_users().get(user, False))
