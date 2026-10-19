import json, requests, traceback
OUT=[]
def note(m): OUT.append(str(m).replace("\n"," ")[:1500])
try:
    UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
    s=requests.Session(); s.headers.update({"User-Agent":UA,"Accept-Language":"en-MY,en;q=0.9"})
    pages={"MJXQ4X/A":"https://www.apple.com/my/shop/buy-iphone/iphone-18-pro/6.9-inch-display-256gb-burgundy","MK2E4X/A":"https://www.apple.com/my/shop/buy-iphone/iphone-duo","MJRR4X/A":"https://www.apple.com/my/shop/buy-iphone/iphone-18-pro"}
    avail=[]
    for q,pg in pages.items():
        s.headers["Referer"]=pg; s.get(pg,timeout=20)
        r=s.get("https://www.apple.com/my/shop/pickup-message-recommendations",params={"mts.0":"regular","mts.1":"compact","location":"55188","product":q},timeout=20)
        pm=(r.json().get("body") or {}).get("PickupMessage") or {}
        for st in pm.get("stores",[]):
            for pn,i in (st.get("partsAvailability") or {}).items():
                t=((i.get("messageTypes") or {}).get("regular") or {}).get("storePickupProductTitle","").replace(" "," ")
                note(f"RECS q={q} {pn} {t} | {i.get('pickupDisplay')} | {i.get('pickupSearchQuote')} | storePickEligible={i.get('storePickEligible')} | lastFetched={st.get('retailStore',{}).get('lastFetched')}")
                avail.append((pn,pg))
        if not pm.get("stores"): note(f"RECS q={q} none")
    for pn,pg in (avail[:4] or [("MJXQ4X/A",pages["MJXQ4X/A"]),("MK2E4X/A",pages["MK2E4X/A"])]):
        s.headers["Referer"]=pg
        for params in [{"parts.0":pn,"location":"55188","mts.0":"regular"},{"parts.0":pn,"store":"R742","mts.0":"regular"},{"product":pn,"location":"55188"}]:
            r=s.get("https://www.apple.com/my/shop/sba/availability-message",params=params,timeout=20)
            note(f"SBA {pn} {list(params)} {r.status_code} {r.text[:600]}")
        r=s.get("https://www.apple.com/my/shop/sba/pickup-detail",params={"parts.0":pn,"store":"R742"},timeout=20)
        note(f"PDET {pn} {r.status_code} {r.text[:400]}")
except Exception: note(traceback.format_exc())
txt=" || ".join(OUT)
for i in range(0,min(len(txt),9*3000),3000): print("::notice::"+txt[i:i+3000])
