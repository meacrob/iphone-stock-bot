import re, json, requests
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
                  "Accept-Language": "en-MY,en;q=0.9"})
def note(m): print("::notice::" + str(m).replace("\n", " ")[:900], flush=True)
page = "https://www.apple.com/my/shop/buy-iphone/iphone-18-pro"
r = s.get(page, timeout=20); note(f"page {r.status_code} len {len(r.text)}")
html = r.text
parts = sorted(set(re.findall(r'"([A-Z0-9]{4,6}X/A)"', html)))
note(f"X/A parts on page ({len(parts)}): {' '.join(parts)}")
# try to read product titles via fulfillment for all parts (batch)
params = {"fae":"true","pl":"true","mts.0":"regular","location":"55188"}
for i,p in enumerate(parts[:40]): params[f"parts.{i}"]=p
try:
    j = s.get("https://www.apple.com/my/shop/fulfillment-messages", params=params, timeout=20).json()
    stores = j["body"]["content"]["pickupMessage"].get("stores", [])
    note(f"stores: {[st.get('storeName') for st in stores]}")
    if stores:
        pa = stores[0].get("partsAvailability", {})
        for p, info in pa.items():
            t = (info.get("messageTypes", {}).get("regular", {}) or {}).get("storePickupProductTitle", "?")
            if "Max" in t and ("Burgundy" in t or "burgundy" in t.lower()):
                note(f"MATCH {p} = {t} | {info.get('pickupDisplay')}")
        note("all titles: " + " ; ".join(f"{p}={(i.get('messageTypes',{}).get('regular',{}) or {}).get('storePickupProductTitle','?')}" for p,i in pa.items()))
    else:
        note("raw: " + json.dumps(j)[:800])
except Exception as e:
    note(f"fulfillment error {e}")
