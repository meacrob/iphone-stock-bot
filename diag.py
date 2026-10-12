import json, requests
def note(m): print("::notice::" + str(m).replace("\n", " ")[:900], flush=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
s = requests.Session(); s.headers.update({"User-Agent": UA, "Accept-Language": "en-MY,en;q=0.9"})
s.get("https://www.apple.com/my/shop/buy-iphone/iphone-18-pro", timeout=20)  # get cookies
tests = {
 "fm_location": ("https://www.apple.com/my/shop/fulfillment-messages", {"fae":"true","pl":"true","mts.0":"regular","parts.0":"MJXQ4X/A","location":"55188"}),
 "fm_nofae": ("https://www.apple.com/my/shop/fulfillment-messages", {"pl":"true","mts.0":"regular","parts.0":"MJXQ4X/A","location":"55188"}),
 "fm_little": ("https://www.apple.com/my/shop/fulfillment-messages", {"little":"false","parts.0":"MJXQ4X/A","mts.0":"regular","mts.1":"sticky","fts":"true","searchNearby":"true","location":"55188"}),
 "retail_avail": ("https://www.apple.com/my/shop/retail/pickup-message", {"pl":"true","parts.0":"MJXQ4X/A","location":"55188"}),
}
for name,(url,params) in tests.items():
    try:
        r = s.get(url, params=params, timeout=20, headers={"Referer":"https://www.apple.com/my/shop/buy-iphone/iphone-18-pro","Accept":"application/json"})
        body = r.text
        try:
            j = r.json(); pm = j.get("body",{}).get("content",{}).get("pickupMessage",{})
            st = pm.get("stores",[])
            summ = [(x.get("storeName"), {p:(i.get("pickupDisplay"), (i.get("messageTypes",{}).get("regular",{}) or {}).get("storePickupProductTitle")) for p,i in (x.get("partsAvailability") or {}).items()}) for x in st]
            note(f"{name} {r.status_code} JSON stores={summ} keys={list(pm.keys())[:10]} errors={pm.get('errorMessage')}")
        except Exception:
            note(f"{name} {r.status_code} ct={r.headers.get('content-type')} body={body[:300]}")
    except Exception as e:
        note(f"{name} EXC {e}")
