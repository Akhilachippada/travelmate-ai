"""TravelMate AI – LangGraph multi-agent planner (Supervisor + 6 specialist agents)."""
import os, re, math, copy, uuid, datetime as dt
from typing import TypedDict
import httpx
from langgraph.graph import StateGraph, START, END

W = "https://commons.wikimedia.org/wiki/Special:FilePath/"
def A(n, d, h, c, tags, lat, lon, out=True): return dict(name=n, desc=d, dur=h, cost=c, tags=tags.split(), lat=lat, lon=lon, outdoor=out)
DEST = {
 "kerala": dict(name="Kerala", emoji="🌴", lat=9.93, lon=76.27, tags="beach nature adventure food culture relax", season="Oct–Mar",
   img=W+"Alleppey_Backwaters.jpg?width=900", blurb="God's Own Country: backwaters, beaches, tea hills and spice-laden cuisine.",
   hidden="Kumbalangi & Vagamon meadows", acts=[
   A("Alleppey Houseboat Cruise","Drift through palm-lined backwaters",4,1800,"nature relax food",9.49,76.33),
   A("Kovalam Beach","Crescent beach, lighthouse sunset",3,300,"beach relax",8.40,76.98),
   A("Munnar Tea Gardens","Rolling tea estates and misty viewpoints",4,500,"nature adventure",10.09,77.06),
   A("Athirappilly Waterfalls","The 'Niagara of India'",2.5,100,"nature adventure",10.285,76.57),
   A("Fort Kochi & Chinese Nets","Heritage lanes, street art, seafood",3,400,"culture food",9.96,76.24,False),
   A("Kathakali Performance","Classical dance-drama with makeup demo",1.5,350,"culture relax",9.97,76.28,False),
   A("Varkala Cliff Paragliding","Cliff-top views over the Arabian Sea",2,2500,"adventure beach",8.73,76.70),
   A("Ayurvedic Spa Session","Traditional Kerala massage",2,1500,"relax",9.93,76.27,False)]),
 "goa": dict(name="Goa", emoji="🏖️", lat=15.30, lon=74.12, tags="beach food adventure shopping relax culture", season="Nov–Feb",
   img=W+"Baga_Beach_Goa.jpg?width=900", blurb="Sun, sand, Portuguese heritage and legendary seafood shacks.",
   hidden="Palolem & Butterfly Beach", acts=[
   A("Baga & Calangute Beach","Watersports and beach shacks",4,800,"beach adventure food",15.55,73.75),
   A("Basilica of Bom Jesus","UNESCO-listed baroque church",1.5,0,"culture",15.50,73.91,False),
   A("Fort Aguada Sunset","17th-century fort & lighthouse",2,50,"culture beach",15.49,73.77),
   A("Dudhsagar Falls Jeep Safari","Four-tiered jungle waterfall",5,1200,"nature adventure",15.31,74.31),
   A("Anjuna Flea Market","Shopping & street food",3,500,"shopping food",15.58,73.74,False),
   A("Palolem Beach Kayaking","Calm crescent bay",3,600,"beach relax",15.01,74.02),
   A("Panjim Latin Quarter Walk","Fontainhas colourful lanes",2.5,200,"culture food",15.49,73.83)]),
 "jaipur": dict(name="Jaipur, Rajasthan", emoji="🏰", lat=26.91, lon=75.79, tags="culture shopping food adventure", season="Oct–Mar",
   img=W+"Hawa_Mahal_2011.jpg?width=900", blurb="The Pink City: palaces, forts and bazaars.",
   hidden="Abhaneri Stepwell", acts=[
   A("Amber Fort","Hilltop fort with mirror palace",3,550,"culture adventure",26.99,75.85),
   A("Hawa Mahal","Palace of Winds facade",1,200,"culture",26.92,75.83,False),
   A("City Palace & Jantar Mantar","Royal museum and astronomy park",3,700,"culture",26.93,75.82,False),
   A("Johari Bazaar Shopping","Jewellery, textiles, lac bangles",3,1000,"shopping food",26.92,75.82,False),
   A("Nahargarh Sunset","Panoramic city views",2,200,"nature relax",26.94,75.81),
   A("Chokhi Dhani Dinner","Rajasthani village-style feast",3,900,"food culture relax",26.77,75.85,False)]),
 "manali": dict(name="Manali, Himachal", emoji="🏔️", lat=32.24, lon=77.19, tags="adventure nature relax food", season="Mar–Jun, Oct–Nov",
   img=W+"Manali_Himachal_Pradesh.jpg?width=900", blurb="Snow peaks, pine forests and adrenaline.",
   hidden="Jogini & Naggar Castle", acts=[
   A("Solang Valley Adventure","Paragliding, zorbing, ropeway",4,2000,"adventure nature",32.32,77.15),
   A("Hadimba Temple","Cedar-forest wooden temple",1.5,0,"culture nature",32.25,77.18),
   A("Rohtang / Atal Tunnel Drive","Snow-capped pass views",6,1500,"nature adventure",32.37,77.24),
   A("Old Manali Cafés","Riverside cafés & Tibetan food",3,600,"food relax",32.26,77.18,False),
   A("Beas River Rafting","Grade II–III rapids",2.5,1200,"adventure",32.12,77.12),
   A("Vashisht Hot Springs","Natural sulphur baths",2,100,"relax culture",32.27,77.19)]),
 "andaman": dict(name="Andaman Islands", emoji="🐠", lat=11.62, lon=92.73, tags="beach adventure nature relax", season="Nov–May",
   img=W+"Radhanagar_Beach_Havelock.jpg?width=900", blurb="Turquoise water, coral reefs and white sand.",
   hidden="Neil Island's Bharatpur", acts=[
   A("Radhanagar Beach","Asia's best-rated beach",4,0,"beach relax",11.98,92.95),
   A("Scuba Diving, Havelock","Coral reef dive",3,3500,"adventure beach",11.97,92.99),
   A("Cellular Jail Light Show","Colonial history museum",2.5,300,"culture",11.67,92.75,False),
   A("Elephant Beach Snorkelling","Boat ride and reef",3,1500,"adventure beach",12.02,92.97),
   A("Ross Island Ruins","Overgrown British ruins",2.5,300,"culture nature",11.68,92.77)]),
}
CITIES = {"vijayawada":(16.51,80.65),"hyderabad":(17.38,78.48),"chennai":(13.08,80.27),"bangalore":(12.97,77.59),"delhi":(28.61,77.21),"mumbai":(19.07,72.88),"kolkata":(22.57,88.36),"visakhapatnam":(17.69,83.22)}
INTERESTS = "beach nature adventure culture shopping food relax".split()
NUM = dict(one=1,two=2,three=3,four=4,five=5,six=6,seven=7,eight=8)

def hav(a, b, c, d):
    p = math.pi/180; x = math.sin((c-a)*p/2)**2 + math.cos(a*p)*math.cos(c*p)*math.sin((d-b)*p/2)**2
    return 12742*math.asin(math.sqrt(x))

def parse_request(text, prefs=None):
    t = text.lower(); r = {"interests": [i for i in INTERESTS if i in t or (i=="beach" and "beaches" in t) or (i=="adventure" and "trek" in t)]}
    if prefs and not r["interests"]: r["interests"] = prefs.get("interests", [])
    m = re.search(r"(\d+)[- ]day", t); r["days"] = int(m.group(1)) if m else None
    m = re.search(r"(\d+|one|two|three|four|five|six|seven|eight)\s*(?:people|persons|travell?ers|adults|friends|of us)", t)
    r["travelers"] = int(m.group(1)) if m and m.group(1).isdigit() else NUM.get(m.group(1)) if m else None
    m = re.search(r"(?:₹|rs\.?|inr)\s*([\d,]+)", t) or re.search(r"budget[^\d]{0,20}([\d,]{4,})", t)
    r["budget"] = int(m.group(1).replace(",", "")) if m else None
    m = re.search(r"from\s+([a-z ]+?)(?:\s+for|\s+to|\.|,|$)", t); r["origin"] = m.group(1).strip().title() if m else None
    r["destination"] = next((k for k, v in DEST.items() if k in t or v["name"].split(",")[0].lower() in t), None)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", t); r["start"] = m.group(1) if m else None
    return r

def validate_req(r):
    q = []
    if not r.get("origin"): q.append("Where are you starting from?")
    if not r.get("budget"): q.append("What is your total budget (₹)?")
    if not r.get("travelers"): q.append("How many travelers?")
    if not (r.get("days") or (r.get("start") and r.get("end"))): q.append("How many days (or start/end dates)?")
    if r.get("days") and r["days"] > 14: q.append("Trips over 14 days are unusual – please confirm.")
    if r.get("budget") and r.get("travelers") and r["budget"]/r["travelers"] < 3000: q.append("Budget under ₹3,000 per person is likely too low for transport + stay – increase or confirm.")
    return q

class S(TypedDict, total=False):
    req: dict; dkey: str; dest: dict; transport: dict; stay: dict; weather: list; itinerary: list; budget: dict; issues: list

def supervisor(s):
    r = dict(s["req"]); today = dt.date.today()
    start = dt.date.fromisoformat(r["start"]) if r.get("start") else today + dt.timedelta(days=14)
    if r.get("end"): days = (dt.date.fromisoformat(r["end"]) - start).days + 1
    else: days = r.get("days") or 4
    r.update(start=start.isoformat(), days=days, end=(start+dt.timedelta(days=days-1)).isoformat(), travelers=r.get("travelers") or 2,
             origin=r.get("origin") or "Vijayawada", budget=r.get("budget") or 20000*(r.get("travelers") or 2))
    issues = []
    if not s["req"].get("start"): issues.append("No start date given – assumed 14 days from today.")
    dk = r.get("destination") if r.get("destination") in DEST else max(DEST, key=lambda k: len(set(DEST[k]["tags"].split()) & set(r["interests"] or INTERESTS[:3])))  # Destination Research
    return {"req": r, "dkey": dk, "dest": {k: v for k, v in DEST[dk].items() if k != "acts"}, "issues": issues}

def destination_agent(s):
    d = DEST[s["dkey"]]; it = set(s["req"]["interests"])
    match = sorted(it & set(d["tags"].split()))
    return {"dest": {**s["dest"], "why": f"Matches your interest in {', '.join(match) or 'exploration'}; best season {d['season']}.",
            "alternatives": [DEST[k]["name"] for k in DEST if k != s["dkey"] and it & set(DEST[k]["tags"].split())][:3]}}

def transport_agent(s):
    r, d = s["req"], DEST[s["dkey"]]; o = CITIES.get(r["origin"].lower(), CITIES["vijayawada"])
    km = round(hav(*o, d["lat"], d["lon"])*1.3)
    modes = [dict(mode="Sleeper train / bus", hours=round(km/50,1), pp_round_trip=round(km*2*0.7)),
             dict(mode="AC train", hours=round(km/60,1), pp_round_trip=round(km*2*1.4)),
             dict(mode="Flight", hours=round(km/600+3,1), pp_round_trip=round(km*2*3.5+1500))]
    return {"transport": dict(km=km, modes=modes, verified=False, note="Approximate estimates from route distance – no provider API connected; verify fares before booking.")}

def accommodation_agent(s):
    return {"stay": dict(verified=False, note="Estimated price bands only – no live availability/prices are shown.",
        categories=[dict(tier="Budget", type="Hostel / homestay", per_room=800), dict(tier="Balanced", type="3★ hotel / resort cottage", per_room=2200), dict(tier="Comfortable", type="4★ resort / houseboat stay", per_room=4800)])}

def fetch_weather(lat, lon, start, days):
    out = []; s0 = dt.date.fromisoformat(start)
    try:
        if (s0 - dt.date.today()).days > 15: raise ValueError("beyond forecast")
        j = httpx.get("https://api.open-meteo.com/v1/forecast", params=dict(latitude=lat, longitude=lon, daily="temperature_2m_max,precipitation_probability_max",
            timezone="auto", start_date=start, end_date=(s0+dt.timedelta(days=days-1)).isoformat()), timeout=6).json()["daily"]
        for i, d in enumerate(j["time"]): out.append(dict(date=d, tmax=j["temperature_2m_max"][i], rain=j["precipitation_probability_max"][i], source="Open-Meteo forecast"))
    except Exception:
        monsoon = s0.month in (6,7,8,9)
        out = [dict(date=(s0+dt.timedelta(days=i)).isoformat(), tmax=None, rain=70 if monsoon else 15, source="Seasonal estimate (forecast unavailable)") for i in range(days)]
    for w in out: w["bad"] = (w["rain"] or 0) >= 60; w["note"] = "Rain likely – outdoor plans swapped for indoor ones." if w["bad"] else "Good for outdoor activities."
    return out

def weather_agent(s):
    d = DEST[s["dkey"]]; return {"weather": fetch_weather(d["lat"], d["lon"], s["req"]["start"], s["req"]["days"])}

def mk(a, day, time, prev):
    km = round(hav(prev[0], prev[1], a["lat"], a["lon"])*1.3) if prev else 0
    return {**a, "id": uuid.uuid4().hex[:8], "time": time, "travel_km": km, "travel_min": round(km/35*60), "note": ""}

def score(a, it): return len(set(a["tags"]) & set(it))

def build_day(dkey, day_i, used, interests, weather, pace="balanced", style=None, light=False):
    n = {"relaxed": 2, "balanced": 3, "packed": 4}.get(pace, 3) - (1 if light else 0)
    bad = weather and weather["bad"]; pool = [a for a in DEST[dkey]["acts"] if a["name"] not in used]
    if bad: pool = [a for a in pool if not a["outdoor"]] or pool
    want = [style] if style else interests
    pool.sort(key=lambda a: -score(a, want)); picks = pool[:n]; slots = ["09:00", "13:30", "16:30", "19:00"]; acts = []; prev = None
    for a, t in zip(picks, slots):
        x = mk(a, day_i, t, prev); prev = (a["lat"], a["lon"]); used.add(a["name"])
        if bad and not a["outdoor"]: x["note"] = "☔ Weather-aware indoor pick"
        acts.append(x)
    return acts

def itinerary_agent(s):
    r, used, days = s["req"], set(), []; start = dt.date.fromisoformat(r["start"])
    for i in range(r["days"]):
        w = s["weather"][i] if i < len(s["weather"]) else None
        acts = build_day(s["dkey"], i+1, used, r["interests"] or INTERESTS[:3], w, r.get("pace", "balanced"), light=(i == 0 or i == r["days"]-1))
        days.append(dict(day=i+1, date=(start+dt.timedelta(days=i)).isoformat(), location=DEST[s["dkey"]]["name"], weather=w, activities=acts))
    return {"itinerary": days}

def budget_for(r, dkey, days, transport):
    n, nights = r["travelers"], max(r["days"]-1, 1); rooms = math.ceil(n/2); act = sum(a["cost"] for d in days for a in d["activities"])*n
    sc = {}
    for i, (name, stay, food, tmode) in enumerate([("Budget-friendly", 800, 350, 0), ("Balanced", 2200, 700, 1), ("Comfortable", 4800, 1300, 2)]):
        b = dict(Transportation=transport["modes"][tmode]["pp_round_trip"]*n, Accommodation=stay*rooms*nights, Food=food*n*r["days"], Activities=round(act*(1+0.15*i)))
        sub = sum(b.values()); b["Shopping"] = round(sub*0.05); b["Miscellaneous"] = round(sub*0.05); tot = sum(b.values())
        sc[name] = dict(breakdown=b, total=tot, per_person=round(tot/n), within=tot <= r["budget"], mode=transport["modes"][tmode]["mode"])
    return sc

def budget_agent(s):
    sc = budget_for(s["req"], s["dkey"], s["itinerary"], s["transport"]); r = s["req"]; tips = []
    ok = [k for k, v in sc.items() if v["within"]]
    if not ok: tips.append("Even the budget-friendly scenario exceeds your budget – shorten the trip, pick sleeper train/bus, or use hostels.")
    else: tips.append(f"Best fit within ₹{r['budget']:,}: {ok[-1]}.")
    tips += ["Travel mid-week and book trains 60+ days ahead.", "Share rooms (triple occupancy) and eat at local joints to cut 15–25%."]
    return {"budget": dict(scenarios=sc, recommended=ok[-1] if ok else "Budget-friendly", tips=tips, currency="INR", estimated=True)}

def validator(s):
    iss = list(s.get("issues", []))
    for d in s["itinerary"]:
        if sum(a["dur"] for a in d["activities"]) > 11: iss.append(f"Day {d['day']} may be too exhausting.")
        if d["weather"] and d["weather"]["bad"]: iss.append(f"Day {d['day']}: rain forecast – itinerary re-planned indoors (Weather ↔ Supervisor loop).")
    if not s["budget"]["scenarios"][s["budget"]["recommended"]]["within"]: iss.append("Budget exceeded in all scenarios.")
    return {"issues": iss}

g = StateGraph(S); g.add_node("supervisor", supervisor)
for n, f in dict(destination=destination_agent, transport=transport_agent, accommodation=accommodation_agent, weather=weather_agent).items(): g.add_node(n, f); g.add_edge("supervisor", n)
g.add_node("itinerary", itinerary_agent); g.add_node("budget", budget_agent); g.add_node("validator", validator)
g.add_edge(START, "supervisor"); g.add_edge(["destination", "transport", "accommodation", "weather"], "itinerary")  # parallel fan-out / join
g.add_edge("itinerary", "budget"); g.add_edge("budget", "validator"); g.add_edge("validator", END); GRAPH = g.compile()

def plan_trip(req):
    s = GRAPH.invoke({"req": req})
    return dict(req=s["req"], dkey=s["dkey"], dest=s["dest"], transport=s["transport"], stay=s["stay"], weather=s["weather"], itinerary=s["itinerary"], budget=s["budget"], issues=s["issues"])

def rebudget(p):
    p["budget"]["scenarios"] = budget_for(p["req"], p["dkey"], p["itinerary"], p["transport"]); return p

def regen_day(p, day, style=None):
    used = {a["name"] for d in p["itinerary"] if d["day"] != day for a in d["activities"]}; d = p["itinerary"][day-1]
    d["activities"] = build_day(p["dkey"], day, used, p["req"]["interests"] or INTERESTS[:3], d["weather"], p["req"].get("pace", "balanced"), style)
    return rebudget(p)

def regen_activity(p, day, idx, style=None):
    used = {a["name"] for d in p["itinerary"] for a in d["activities"]}; old = p["itinerary"][day-1]["activities"][idx]
    pool = [a for a in DEST[p["dkey"]]["acts"] if a["name"] not in used and (not style or style in a["tags"])]
    if not pool: return p, False
    new = mk(max(pool, key=lambda a: score(a, p["req"]["interests"])), day, old["time"], None); p["itinerary"][day-1]["activities"][idx] = new
    return rebudget(p), True

def nl_edit(p, text):
    t = text.lower(); m = re.search(r"day\s*(\d+)", t)
    if not m or int(m.group(1)) > len(p["itinerary"]): return p, "Please mention a valid day, e.g. 'Replace the adventure activity on Day 3 with a relaxing activity'."
    day = int(m.group(1)); alias = dict(relaxing="relax", relax="relax", adventure="adventure", adventurous="adventure", cultural="culture", culture="culture", food="food", beach="beach", nature="nature", shopping="shopping")
    parts = re.split(r"\bwith\b|\bto\b|\binstead\b", t); src = next((alias[w] for w in re.findall(r"\w+", parts[0]) if w in alias), None)
    dst = next((alias[w] for w in re.findall(r"\w+", " ".join(parts[1:])) if w in alias), None)
    acts = p["itinerary"][day-1]["activities"]; idx = next((i for i, a in enumerate(acts) if src in a["tags"]), 0) if src else 0
    p, ok = regen_activity(p, day, idx, dst)
    return p, (f"Replaced '{acts[idx]['name']}' on Day {day} with a {dst or 'new'} activity; other days untouched." if ok else "No unused matching activity left for that style.")

def chat_reply(msg, plan=None):
    key = os.getenv("ANTHROPIC_API_KEY")
    ctx = f"Current plan: {plan['dest']['name']}, {plan['req']['days']} days, budget ₹{plan['req']['budget']}" if plan else "No trip yet."
    if key:
        try:
            import anthropic
            r = anthropic.Anthropic(api_key=key).messages.create(model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"), max_tokens=500,
                system="You are TravelMate AI, a concise Indian travel assistant. Never invent hotel prices/availability. " + ctx, messages=[{"role": "user", "content": msg}])
            return r.content[0].text
        except Exception as e: pass
    m = msg.lower()
    if "budget" in m and plan: return f"Recommended scenario: {plan['budget']['recommended']}. " + " ".join(plan["budget"]["tips"])
    if "weather" in m and plan: return "; ".join(f"{w['date']}: {w['rain']}% rain" for w in plan["weather"])
    if any(k in m for k in ("best time", "season")): return "Kerala/Goa/Jaipur: Oct–Mar. Manali: Mar–Jun & Oct–Nov. Andaman: Nov–May."
    return "I can plan trips, tweak days ('Replace adventure on Day 3 with relaxing'), compare budgets and check weather. Set ANTHROPIC_API_KEY for full LLM chat."
