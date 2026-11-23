import os, json, sqlite3, hashlib, secrets, datetime as dt
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import jwt
from agents import *

SECRET = os.getenv("JWT_SECRET", "change-me")
db = sqlite3.connect("travelmate.db", check_same_thread=False); db.row_factory = sqlite3.Row
db.executescript("""create table if not exists users(id integer primary key,email text unique,name text,pw text,prefs text default '{}',favs text default '[]');
create table if not exists trips(id integer primary key,uid int,plan text,created text);
create table if not exists versions(id integer primary key,tid int,plan text,note text,created text);""")
app = FastAPI(title="TravelMate AI")
now = lambda: dt.datetime.utcnow().isoformat(timespec="seconds")

def hpw(p, salt=None):
    salt = salt or secrets.token_hex(8); return salt + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), salt.encode(), 120000).hex()
def user(auth):
    try: return db.execute("select * from users where id=?", (jwt.decode((auth or "").replace("Bearer ", ""), SECRET, algorithms=["HS256"])["uid"],)).fetchone()
    except Exception: raise HTTPException(401, "Not authenticated")
def tok(u): return jwt.encode({"uid": u["id"], "exp": dt.datetime.utcnow()+dt.timedelta(days=7)}, SECRET)
def get_trip(tid, auth):
    u = user(auth); r = db.execute("select * from trips where id=? and uid=?", (tid, u["id"])).fetchone()
    if not r: raise HTTPException(404, "Trip not found")
    return json.loads(r["plan"])
def save(tid, plan, note):
    db.execute("update trips set plan=? where id=?", (json.dumps(plan), tid)); db.execute("insert into versions(tid,plan,note,created) values(?,?,?,?)", (tid, json.dumps(plan), note, now())); db.commit(); return plan

class Auth(BaseModel): email: str; password: str; name: str = ""
class Text(BaseModel): text: str
class Req(BaseModel): text: str = ""; form: dict = {}
class Act(BaseModel): day: int; name: str = "Custom activity"; desc: str = ""; dur: float = 1; cost: float = 0; time: str = "10:00"
class Edit(BaseModel): name: str | None = None; desc: str | None = None; dur: float | None = None; cost: float | None = None; time: str | None = None
class Move(BaseModel): day: int; idx: int; to_day: int; to_idx: int
class Style(BaseModel): style: str | None = None
class Chat(BaseModel): message: str; trip_id: int | None = None
class Whatif(BaseModel): budget: int

@app.post("/api/register")
def register(a: Auth):
    try: c = db.execute("insert into users(email,name,pw) values(?,?,?)", (a.email.lower(), a.name or a.email.split("@")[0], hpw(a.password))); db.commit()
    except sqlite3.IntegrityError: raise HTTPException(400, "Email already registered")
    return {"token": tok({"id": c.lastrowid}), "name": a.name}
@app.post("/api/login")
def login(a: Auth):
    u = db.execute("select * from users where email=?", (a.email.lower(),)).fetchone()
    if not u or hpw(a.password, u["pw"].split("$")[0]) != u["pw"]: raise HTTPException(401, "Invalid credentials")
    return {"token": tok(u), "name": u["name"]}
@app.get("/api/me")
def me(authorization: str = Header(None)):
    u = user(authorization); return dict(email=u["email"], name=u["name"], prefs=json.loads(u["prefs"]), favs=json.loads(u["favs"]))
@app.put("/api/me")
def upd_me(b: dict, authorization: str = Header(None)):
    u = user(authorization)
    if b.get("password"): db.execute("update users set pw=? where id=?", (hpw(b["password"]), u["id"]))
    db.execute("update users set name=?, prefs=? where id=?", (b.get("name", u["name"]), json.dumps(b.get("prefs", {})), u["id"])); db.commit(); return {"ok": True}
@app.post("/api/favs/{key}")
def fav(key: str, authorization: str = Header(None)):
    u = user(authorization); f = set(json.loads(u["favs"])); f ^= {key}; db.execute("update users set favs=? where id=?", (json.dumps(sorted(f)), u["id"])); db.commit(); return sorted(f)
@app.get("/api/destinations")
def dests(): return {k: {x: y for x, y in v.items() if x != "acts"} | {"count": len(v["acts"])} for k, v in DEST.items()}

@app.post("/api/parse")
def parse(t: Text, authorization: str = Header(None)):
    p = json.loads(user(authorization)["prefs"]); r = parse_request(t.text, p); return {"req": r, "questions": validate_req(r)}
@app.post("/api/trips")
def create(b: Req, authorization: str = Header(None)):
    u = user(authorization); r = {**parse_request(b.text, json.loads(u["prefs"])), **{k: v for k, v in b.form.items() if v not in (None, "", [])}}
    q = validate_req(r)
    if q and not b.form.get("force"): return {"questions": q, "req": r}
    plan = plan_trip(r); c = db.execute("insert into trips(uid,plan,created) values(?,?,?)", (u["id"], json.dumps(plan), now())); db.commit()
    save(c.lastrowid, plan, "Initial plan"); return {"id": c.lastrowid, "plan": plan}
@app.get("/api/trips")
def trips(authorization: str = Header(None)):
    u = user(authorization); return [dict(id=r["id"], created=r["created"], dest=json.loads(r["plan"])["dest"]["name"], days=json.loads(r["plan"])["req"]["days"], img=json.loads(r["plan"])["dest"]["img"]) for r in db.execute("select * from trips where uid=? order by id desc", (u["id"],))]
@app.get("/api/trips/{tid}")
def trip(tid: int, authorization: str = Header(None)): return get_trip(tid, authorization)

def mutate(tid, auth, fn, note):
    p = get_trip(tid, auth); out = fn(p); p = out[0] if isinstance(out, tuple) else p
    return {"plan": save(tid, rebudget(p), note), "msg": out[1] if isinstance(out, tuple) and len(out) > 1 and isinstance(out[1], str) else "Updated"}
@app.post("/api/trips/{tid}/activity")
def add(tid: int, a: Act, authorization: str = Header(None)):
    def f(p):
        p["itinerary"][a.day-1]["activities"].append(dict(id=os.urandom(4).hex(), name=a.name, desc=a.desc, dur=a.dur, cost=a.cost, time=a.time, tags=[], outdoor=False, lat=p["dest"]["lat"], lon=p["dest"]["lon"], travel_km=0, travel_min=0, note="Added by you"))
        return p
    return mutate(tid, authorization, f, f"Added {a.name}")
@app.put("/api/trips/{tid}/activity/{day}/{idx}")
def edit(tid: int, day: int, idx: int, e: Edit, authorization: str = Header(None)):
    def f(p): p["itinerary"][day-1]["activities"][idx].update({k: v for k, v in e.model_dump().items() if v is not None}); return p
    return mutate(tid, authorization, f, f"Edited activity on Day {day}")
@app.delete("/api/trips/{tid}/activity/{day}/{idx}")
def rm(tid: int, day: int, idx: int, authorization: str = Header(None)):
    def f(p): p["itinerary"][day-1]["activities"].pop(idx); return p
    return mutate(tid, authorization, f, f"Removed activity on Day {day}")
@app.post("/api/trips/{tid}/move")
def move(tid: int, m: Move, authorization: str = Header(None)):
    def f(p): a = p["itinerary"][m.day-1]["activities"].pop(m.idx); p["itinerary"][m.to_day-1]["activities"].insert(m.to_idx, a); return p
    return mutate(tid, authorization, f, "Rearranged activities")
@app.post("/api/trips/{tid}/regen-day/{day}")
def rday(tid: int, day: int, s: Style, authorization: str = Header(None)): return mutate(tid, authorization, lambda p: regen_day(p, day, s.style), f"Regenerated Day {day}")
@app.post("/api/trips/{tid}/regen-activity/{day}/{idx}")
def ract(tid: int, day: int, idx: int, s: Style, authorization: str = Header(None)): return mutate(tid, authorization, lambda p: regen_activity(p, day, idx, s.style), f"Regenerated activity Day {day}")
@app.post("/api/trips/{tid}/nl-edit")
def nl(tid: int, t: Text, authorization: str = Header(None)): return mutate(tid, authorization, lambda p: nl_edit(p, t.text), f"AI edit: {t.text[:40]}")
@app.post("/api/trips/{tid}/whatif")
def whatif(tid: int, w: Whatif, authorization: str = Header(None)):
    p = get_trip(tid, authorization); p["req"]["budget"] = w.budget; sc = p["budget"]["scenarios"]
    return {k: dict(v, within=v["total"] <= w.budget, gap=v["total"]-w.budget) for k, v in sc.items()}
@app.get("/api/trips/{tid}/versions")
def versions(tid: int, authorization: str = Header(None)):
    get_trip(tid, authorization); return [dict(r) | {"plan": None} for r in db.execute("select id,note,created from versions where tid=? order by id desc", (tid,))]
@app.post("/api/trips/{tid}/restore/{vid}")
def restore(tid: int, vid: int, authorization: str = Header(None)):
    get_trip(tid, authorization); r = db.execute("select plan from versions where id=? and tid=?", (vid, tid)).fetchone()
    return {"plan": save(tid, json.loads(r["plan"]), f"Restored version {vid}")}
@app.post("/api/chat")
def chat(c: Chat, authorization: str = Header(None)):
    p = get_trip(c.trip_id, authorization) if c.trip_id else None; user(authorization)
    if p and any(k in c.message.lower() for k in ("replace", "swap", "change")) and "day" in c.message.lower():
        r = mutate(c.trip_id, authorization, lambda x: nl_edit(x, c.message), "Chat edit"); return {"reply": r["msg"], "plan": r["plan"]}
    return {"reply": chat_reply(c.message, p)}

app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "frontend"), html=True))
