import re, json, requests, traceback
OUT=[]
def note(m): OUT.append(str(m).replace("\n"," ")[:400])
try:
    s = requests.Session(); s.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36", "Accept-Language": "en-MY,en;q=0.9"})
    url = "https://www.apple.com/my/shop/buy-iphone/iphone-duo"
    html = s.get(url, timeout=20).text
    s.headers["Referer"] = url
    # product titles near part numbers in page JSON
    for m in re.finditer(r'"([A-Z0-9]{4,6}X/A)"\s*:\s*\{', html):
        w = html[m.end(): m.end()+1500]
        t = re.search(r'"(?:productTitle|title|name)"\s*:\s*"([^"]{5,90})"', w)
        note(f"obj {m.group(1)} -> {t.group(1) if t else '?'}")
    slugs = sorted(set(re.findall(r'iphone-duo/[a-z0-9\-]{6,}', html)))
    note("slugs: " + " ".join(slugs[:30]))
    for p in ["MK2D4X/A","MK2E4X/A","MK2F4X/A","MK2G4X/A","MK2H4X/A","MK2J4X/A","MK2K4X/A","MK2L4X/A"]:
        rr = s.get("https://www.apple.com/my/shop/pickup-message-recommendations", params={"mts.0":"regular","mts.1":"compact","location":"55188","product":p}, timeout=20)
        if not rr.text.lstrip().startswith("{"): note(f"recs({p}) {rr.status_code}"); continue
        b = rr.json().get("body") or {}
        pm = b.get("PickupMessage") or {}
        got = [f"{pn}={(i.get('messageTypes',{}).get('regular',{}) or {}).get('storePickupProductTitle')}:{i.get('pickupDisplay')}" for st in pm.get("stores",[]) for pn,i in (st.get("partsAvailability") or {}).items()]
        note(f"recs({p}) -> {got or b.get('noSimilarModelsText','none')}")
except Exception:
    note(traceback.format_exc())
txt=" || ".join(OUT)
for i in range(0, min(len(txt), 9*3000), 3000): print("::notice::"+txt[i:i+3000])
