import json, requests
def note(m): print("::notice::" + str(m).replace("\n", " ")[:1000], flush=True)
PAGE = "https://www.apple.com/my/shop/buy-iphone/iphone-18-pro/6.9-inch-display-256gb-burgundy"
s = requests.Session(); s.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36", "Accept-Language": "en-MY,en;q=0.9", "Referer": PAGE})
s.get(PAGE, timeout=20)
out = {}
r = s.get("https://www.apple.com/my/shop/pickup-message-recommendations", params={"mts.0":"regular","mts.1":"compact","location":"55188","product":"MJXQ4X/A"}, timeout=20)
out["pmr"] = r.json()
r = s.get("https://www.apple.com/my/shop/sba/availability-message", params={"parts.0":"MJXQ4X/A","location":"55188","mts.0":"regular"}, timeout=20)
out["sba"] = r.json()
r = s.get("https://www.apple.com/my/shop/pickup-message-recommendations", params={"mts.0":"regular","mts.1":"compact","location":"55188","product":"MJXQ4X/A","cppart":"UNLOCKED/WW"}, timeout=20)
out["pmr2_status"] = r.status_code
txt = json.dumps(out)
note(f"total len {len(txt)}")
for i in range(0, min(len(txt), 9000), 950):
    note(f"{i:05d} " + txt[i:i+950])
