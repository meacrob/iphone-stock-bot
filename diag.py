import re, json, requests
OUT=[]
def note(m): OUT.append(str(m).replace("\n"," ")[:400])
s = requests.Session(); s.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36", "Accept-Language": "en-MY,en;q=0.9"})
h = s.get("https://www.apple.com/my/shop/buy-iphone", timeout=20).text
links = sorted(set(re.findall(r'/my/shop/buy-iphone/[a-z0-9\-]+', h)))
note("buy links: " + " ".join(links))
for path in [l for l in links if "duo" in l] or ["/my/shop/buy-iphone/iphone-duo"]:
    url = "https://www.apple.com" + path
    r = s.get(url, timeout=20); note(f"{url} {r.status_code} len {len(r.text)}")
    html = r.text
    for m in re.finditer(r'"partNumber"\s*:\s*"([A-Z0-9]{4,6}X/A)"', html):
        w = html[max(0,m.start()-700):m.end()+700]
        cap = re.search(r'"dimensionCapacity"\s*:\s*"(\w+)"', w); col = re.search(r'"dimensionColor"\s*:\s*"([\w\-]+)"', w)
        note(f"PART {m.group(1)} cap={cap.group(1) if cap else '?'} color={col.group(1) if col else '?'}")
    slugs = sorted(set(re.findall(re.escape(path) + r'/[a-z0-9\-]+', html)))
    note("slugs: " + " ".join(slugs[:30]))
    # titles via recs
    parts = sorted(set(re.findall(r'"([A-Z0-9]{4,6}X/A)"', html)))
    note(f"parts on page: {' '.join(parts)}")
    s.headers["Referer"] = url
    for p in parts[:3]:
        rr = s.get("https://www.apple.com/my/shop/pickup-message-recommendations", params={"mts.0":"regular","mts.1":"compact","location":"55188","product":p}, timeout=20)
        try:
            pm = rr.json()["body"].get("PickupMessage") or {}
            for st in pm.get("stores", []):
                for pn, i in (st.get("partsAvailability") or {}).items():
                    note(f"recs({p}) {pn} {(i.get('messageTypes',{}).get('regular',{}) or {}).get('storePickupProductTitle')} {i.get('pickupDisplay')}")
            if not pm.get("stores"): note(f"recs({p}) no stores: {json.dumps(rr.json()['body'])[:200]}")
        except Exception as e: note(f"recs({p}) {rr.status_code} {rr.text[:80]}")

txt=" || ".join(OUT)
for i in range(0, min(len(txt), 9*3000), 3000): print("::notice::"+txt[i:i+3000])
