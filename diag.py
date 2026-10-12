import re, requests
def note(m): print("::notice::" + str(m).replace("\n", " ")[:900], flush=True)
s = requests.Session(); s.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36", "Accept-Language": "en-MY,en;q=0.9"})
html = s.get("https://www.apple.com/my/shop/buy-iphone/iphone-18-pro/6.9-inch-display-256gb-burgundy", timeout=20).text
note(f"len {len(html)}")
hits = sorted(set(re.findall(r'["\'](/my/shop/[a-zA-Z0-9_\-/]*(?:fulfil|pickup|retail|availability|store|delivery)[a-zA-Z0-9_\-/]*)', html, re.I)))
note("shop urls: " + " | ".join(hits[:40]))
keys = sorted(set(re.findall(r'"([a-zA-Z]*(?:[Ff]ulfil|[Pp]ickup|[Aa]vailab)[a-zA-Z]*)"\s*:\s*"([^"]{0,120})"', html)))
for k,v in keys[:30]: note(f"{k} = {v}")
