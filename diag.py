import json, requests, traceback
OUT=[]
def note(m): OUT.append(str(m))
try:
    UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
    s=requests.Session(); s.headers.update({"User-Agent":UA,"Accept-Language":"en-MY,en;q=0.9"})
    pg="https://www.apple.com/my/shop/buy-iphone/iphone-18-pro"; s.headers["Referer"]=pg; s.get(pg,timeout=20)
    parts=["MJXQ4X/A","MJXV4X/A","MK2D4X/A","MK2E4X/A","MK2F4X/A","MK2G4X/A","MK2H4X/A","MK2J4X/A","MK2K4X/A","MK2L4X/A","MJRP4X/A","MJRQ4X/A","MJRT4X/A","MJRR4X/A","MJRU4X/A","MJRV4X/A"]
    params={"location":"55188","mts.0":"regular"}
    for i,p in enumerate(parts): params[f"parts.{i}"]=p
    r=s.get("https://www.apple.com/my/shop/sba/availability-message",params=params,timeout=20)
    j=r.json(); c=(j.get("body") or {}).get("content") or []
    note(f"MULTI status={r.status_code} n={len(c)}")
    for x in c: note(f"{x.get('partNumber')} stores={x.get('partAvailableStoresCount')} any={x.get('availableAtAnyStore')} keys={list(x.keys())}")
    note("FULL0 "+json.dumps(c[0] if c else j)[:2500])
except Exception: note(traceback.format_exc())
txt=" || ".join(OUT)
for i in range(0,min(len(txt),9*3000),3000): print("::notice::"+txt[i:i+3000])
