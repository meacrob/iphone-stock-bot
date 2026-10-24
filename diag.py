import requests
s=requests.Session(); s.headers.update({"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36","Accept-Language":"en-MY,en;q=0.9","Referer":"https://www.apple.com/my/shop/buy-iphone/iphone-18-pro"})
s.get("https://www.apple.com/my/shop/buy-iphone/iphone-18-pro",timeout=20)
out=[]
for p in ["MJRP4X/A","MJXQ4X/A","MK2E4X/A","MK2K4X/A"]:
    r=s.get("https://www.apple.com/my/shop/pickup-message-recommendations",params={"mts.0":"regular","mts.1":"compact","location":"55188","product":p},timeout=20)
    b=r.json().get("body") or {}; pm=b.get("PickupMessage") or {}
    got=[f"{(i.get('messageTypes',{}).get('regular',{}) or {}).get('storePickupProductTitle','').replace(chr(160),' ')}:{i.get('pickupSearchQuote')}" for st in pm.get("stores",[]) for i in (st.get("partsAvailability") or {}).values()]
    out.append(f"{p} {r.status_code} -> {got or b.get('noSimilarModelsText')}")
print("::notice::"+" || ".join(out))
