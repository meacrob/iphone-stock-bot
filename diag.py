import requests, time
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
s=requests.Session(); s.headers.update({"User-Agent":UA,"Accept-Language":"en-MY,en;q=0.9"})
out=[]
for u in ["https://www.apple.com/my/","https://www.apple.com/my/shop/bag","https://www.apple.com/my/shop/checkout/start","https://www.apple.com/my/shop/buy-iphone/iphone-duo","https://secure.store.apple.com/my/shop/signIn"]:
    try:
        t=time.time(); r=s.get(u,timeout=25,allow_redirects=True)
        title=r.text.split("<title>")[1].split("</title>")[0].strip()[:70] if "<title>" in r.text else "-"
        out.append(f"{u} -> {r.status_code} final={r.url} {int((time.time()-t)*1000)}ms title='{title}'")
    except Exception as e: out.append(f"{u} -> EXC {e}")
print("::notice::"+" || ".join(out))
