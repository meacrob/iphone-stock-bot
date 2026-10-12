import json
from curl_cffi import requests as cr
import requests as rq
def note(m): print("::notice::" + str(m).replace("\n", " ")[:600], flush=True)
P = "MJXQ4X/A"
REF = "https://www.apple.com/my/shop/buy-iphone/iphone-18-pro"
def summarize(name, r):
    try:
        j = r.json(); pm = j.get("body",{}).get("content",{}).get("pickupMessage",{})
        st = [(x.get("storeName"), {p:(i.get("pickupDisplay"), (i.get("messageTypes",{}).get("regular",{}) or {}).get("storePickupProductTitle"), i.get("pickupSearchQuote")) for p,i in (x.get("partsAvailability") or {}).items()}) for x in pm.get("stores",[])]
        note(f"{name} {r.status_code} JSON {st if st else json.dumps(j)[:400]}")
    except Exception:
        note(f"{name} {r.status_code} {r.text[:120]}")
fm = "https://www.apple.com/my/shop/fulfillment-messages"
q = {"fae":"true","pl":"true","mts.0":"regular","parts.0":P,"location":"55188"}
qs = {"fae":"true","pl":"true","mts.0":"regular","parts.0":P,"store":"R688"}
for imp in ["chrome", "safari", "safari_ios"]:
    try:
        s = cr.Session(impersonate=imp)
        s.get(REF, timeout=20)
        summarize(f"{imp}-loc", s.get(fm, params=q, headers={"Referer":REF}, timeout=20))
    except Exception as e: note(f"{imp} EXC {e}")
# US endpoint with plain requests: is it IP-wide?
r = rq.get("https://www.apple.com/shop/fulfillment-messages", params={"pl":"true","mts.0":"regular","parts.0":"MJXQ4LL/A","location":"10001"}, headers={"User-Agent":"Mozilla/5.0"}, timeout=20)
summarize("plain-US", r)
s = cr.Session(impersonate="chrome")
summarize("chrome-US", s.get("https://www.apple.com/shop/fulfillment-messages", params={"pl":"true","mts.0":"regular","parts.0":"MJXQ4LL/A","location":"10001"}, timeout=20))
