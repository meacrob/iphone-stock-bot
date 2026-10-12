import os, json, requests
def note(m): print("::notice::" + str(m).replace("\n", " ")[:700], flush=True)
u, p = os.environ["PU"], os.environ["PP"]
print(f"::add-mask::{u}"); print(f"::add-mask::{p}")
proxy = f"http://{u}:{p}@gw.dataimpulse.com:823"
for cc in ["", "__cr.my"]:
    px = f"http://{u}{cc}:{p}@gw.dataimpulse.com:823"
    s = requests.Session(); s.proxies = {"http": px, "https": px}
    s.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36", "Accept-Language": "en-MY,en;q=0.9", "Referer": "https://www.apple.com/my/shop/buy-iphone/iphone-18-pro"})
    tag = cc or "any"
    try:
        ip = s.get("https://api.ipify.org?format=json", timeout=30).json(); note(f"[{tag}] exit ip {ip}")
        r = s.get("https://www.apple.com/my/shop/fulfillment-messages", params={"fae":"true","pl":"true","mts.0":"regular","parts.0":"MJXQ4X/A","location":"55188"}, timeout=30)
        try:
            pm = r.json()["body"]["content"]["pickupMessage"]
            st = [(x.get("storeName"), {k:(i.get("pickupDisplay"), (i.get("messageTypes",{}).get("regular",{}) or {}).get("storePickupProductTitle"), i.get("pickupSearchQuote")) for k,i in (x.get("partsAvailability") or {}).items()}) for x in pm.get("stores",[])]
            note(f"[{tag}] APPLE {r.status_code} {st}")
        except Exception:
            note(f"[{tag}] APPLE {r.status_code} {r.text[:150]}")
    except Exception as e:
        note(f"[{tag}] EXC {e}")
