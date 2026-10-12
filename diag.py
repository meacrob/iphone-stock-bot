import os, json, requests
def note(m): print("::notice::" + str(m).replace("\n", " ")[:500], flush=True)
u, p = os.environ["PU"], os.environ["PP"]; print(f"::add-mask::{u}"); print(f"::add-mask::{p}")
PAGE = "https://www.apple.com/my/shop/buy-iphone/iphone-18-pro/6.9-inch-display-256gb-burgundy"
B = "https://www.apple.com/my/shop/"
part = "MJXQ4X/A"
H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
     "Accept-Language": "en-MY,en;q=0.9"}
XH = {"Referer": PAGE, "Accept": "*/*", "x-aos-model-page": "sbaPage", "x-aos-ui-fetch-call-1": "fetch", "x-requested-with": "XMLHttpRequest", "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors", "sec-fetch-dest": "empty"}
calls = {
 "fm": ("fulfillment-messages", {"fae":"true","pl":"true","mts.0":"regular","mts.1":"compact","parts.0":part,"searchNearby":"true","location":"55188"}),
 "fm_store": ("fulfillment-messages", {"pl":"true","mts.0":"regular","mts.1":"compact","parts.0":part,"store":"R688","searchNearby":"true"}),
 "pmr": ("pickup-message-recommendations", {"mts.0":"regular","mts.1":"compact","location":"55188","product":part}),
 "sba_avail": ("sba/availability-message", {"parts.0":part,"location":"55188","mts.0":"regular"}),
 "sba_pickup": ("sba/pickup-detail", {"parts.0":part,"location":"55188"}),
}
for mode in ["direct", "proxy"]:
    s = requests.Session(); s.headers.update(H)
    if mode == "proxy":
        px = f"http://{u}__cr.my:{p}@gw.dataimpulse.com:823"; s.proxies = {"http": px, "https": px}
    try:
        pr = s.get(PAGE, timeout=30); note(f"[{mode}] page {pr.status_code} cookies={list(s.cookies.keys())}")
    except Exception as e: note(f"[{mode}] page EXC {e}"); continue
    for name,(path,params) in calls.items():
        try:
            r = s.get(B+path, params=params, headers=XH, timeout=30)
            t = r.text
            if t.lstrip().startswith("{"):
                j = r.json(); pm = j.get("body",{}).get("content",{}).get("pickupMessage",{}) if isinstance(j.get("body"),dict) else {}
                st = [(x.get("storeName"), {k:(i.get("pickupDisplay"), i.get("pickupSearchQuote")) for k,i in (x.get("partsAvailability") or {}).items()}) for x in pm.get("stores",[])]
                note(f"[{mode}] {name} {r.status_code} JSON stores={st} raw={json.dumps(j)[:250]}")
            else:
                note(f"[{mode}] {name} {r.status_code} {t[:60]}")
        except Exception as e: note(f"[{mode}] {name} EXC {e}")
