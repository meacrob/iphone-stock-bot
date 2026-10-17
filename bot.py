#!/usr/bin/env python3
"""
Apple Store Malaysia pickup tracker -> Telegram alerts.

Runs inside GitHub Actions. Checks Apple TRX pickup availability about once a
minute and messages you on Telegram the moment a watched model is available.

Secrets/env:
  TELEGRAM_TOKEN    bot token from @BotFather (required)
  TELEGRAM_CHAT_ID  optional; otherwise cached / auto-detected
  RUN_MINUTES       how long one run loops before exiting (default 340)
"""

import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
CHAT_FILE = "state/chat_id.txt"
RUN_MINUTES = int(os.environ.get("RUN_MINUTES", "340"))
POLL_SECONDS = (55, 75)
POSTCODE = "55188"  # KL (Apple The Exchange TRX)
MYT = timezone(timedelta(hours=8))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

# ---------------- What to watch ----------------
# A model matches if Apple's product title contains ALL words in "match".
TARGETS = [
    {"name": "iPhone 18 Pro Max 256GB Burgundy",
     "match": ["Pro Max", "256GB", "Burgundy"],
     "url": "https://www.apple.com/my/shop/buy-iphone/iphone-18-pro/6.9-inch-display-256gb-burgundy"},
    {"name": "iPhone 18 Pro Max 512GB Burgundy",
     "match": ["Pro Max", "512GB", "Burgundy"],
     "url": "https://www.apple.com/my/shop/buy-iphone/iphone-18-pro/6.9-inch-display-512gb-burgundy"},
    {"name": "iPhone Duo 256GB (any colour)",
     "match": ["Duo", "256GB"],
     "url": "https://www.apple.com/my/shop/buy-iphone/iphone-duo"},
]
# Apple's feed returns every available model in the same family, so one part
# per family is enough. The extra parts are checked every few rounds as backup.
MAIN_QUERIES = ["MJXQ4X/A", "MK2E4X/A"]    # Pro Max 256 Burgundy, Duo 256
EXTRA_QUERIES = ["MJXV4X/A", "MK2K4X/A"]   # Pro Max 512 Burgundy, Duo 256 (2nd colour)
RECS = "https://www.apple.com/my/shop/pickup-message-recommendations"
WARM_URL = TARGETS[0]["url"]


def log(msg):
    print(f"[{datetime.now(MYT):%H:%M:%S}] {msg}", flush=True)


# ---------------- Telegram ----------------

def tg(method, **params):
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", json=params, timeout=15)
    return r.json()


def get_chat_id():
    cid = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if cid:
        return cid, False
    if os.path.exists(CHAT_FILE):
        return open(CHAT_FILE).read().strip(), False
    for u in reversed(tg("getUpdates").get("result", [])):
        msg = u.get("message") or u.get("edited_message")
        if msg:
            cid = str(msg["chat"]["id"])
            os.makedirs("state", exist_ok=True)
            open(CHAT_FILE, "w").write(cid)
            return cid, True
    sys.exit("No chat found. Send the bot any message on Telegram, then re-run.")


def send(chat_id, text):
    for _ in range(3):
        try:
            if tg("sendMessage", chat_id=chat_id, text=text, disable_web_page_preview=True).get("ok"):
                return
        except Exception as e:
            log(f"telegram failed: {e}")
        time.sleep(5)


# ---------------- Apple ----------------

class Apple:
    def __init__(self):
        self.new_session()

    def new_session(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "en-MY,en;q=0.9", "Referer": WARM_URL})
        try:
            self.s.get(WARM_URL, timeout=20)
        except Exception as e:
            log(f"warm failed: {e}")
        self.born = time.time()

    def check(self, queries):
        """Returns ({(store, target name): (quote, url)}, number of models seen)."""
        hits, seen, ok, last = {}, 0, 0, "?"
        for prod in queries:
            try:
                r = self.s.get(RECS, params={"mts.0": "regular", "mts.1": "compact",
                                             "location": POSTCODE, "product": prod}, timeout=20)
            except Exception as e:
                last = type(e).__name__
                continue
            last = r.status_code
            if r.status_code != 200 or not r.text.lstrip().startswith("{"):
                continue
            ok += 1
            pm = (r.json().get("body") or {}).get("PickupMessage") or {}
            for st in pm.get("stores", []):
                store = st.get("storeName", "?")
                for pn, info in (st.get("partsAvailability") or {}).items():
                    title = (((info.get("messageTypes") or {}).get("regular") or {})
                             .get("storePickupProductTitle", pn)).replace(" ", " ")
                    seen += 1
                    if info.get("pickupDisplay") != "available":
                        continue
                    for t in TARGETS:
                        if all(w in title for w in t["match"]):
                            hits[(store, t["name"])] = (f"{title} - {info.get('pickupSearchQuote', '')}", t["url"])
            time.sleep(random.uniform(2, 5))
        if ok == 0:
            raise RuntimeError(f"Apple returned {last}")
        return hits, seen


# ---------------- Main loop ----------------

def main():
    chat_id, first_time = get_chat_id()
    apple = Apple()
    watching = "\n".join(f"- {t['name']}" for t in TARGETS)
    if first_time or os.environ.get("ANNOUNCE") == "1":
        send(chat_id, f"✅ Tracker updated\nWatching at Apple TRX (every ~1 min):\n{watching}\n\n"
                      f"I'll message you the moment any of these is available for pickup.")

    end = time.time() + RUN_MINUTES * 60
    alerted, fails, down_since, warned, rnd = set(), 0, None, False, 0
    while time.time() < end:
        rnd += 1
        queries = MAIN_QUERIES + (EXTRA_QUERIES if rnd % 3 == 0 else [])
        try:
            if time.time() - apple.born > 1800:
                apple.new_session()
            hits, seen = apple.check(queries)
            if warned:
                send(chat_id, "✅ Apple is responding again, tracking resumed.")
            fails, down_since, warned = 0, None, False
            log(f"ok | seen={seen} | hits={list(hits)}")
            for key, (detail, url) in hits.items():
                if key not in alerted:
                    store, name = key
                    send(chat_id, f"🚨 IN STOCK NOW\n{detail}\n📍 Apple {store}\n\nBuy now 👉 {url}")
                    alerted.add(key)
            alerted &= set(hits)  # re-alert if it sells out and comes back
        except Exception as e:
            fails += 1
            down_since = down_since or time.time()
            log(f"check failed ({fails}): {e}")
            if fails % 3 == 0:
                apple.new_session()  # fresh cookies often clears Apple's 503s
            # Only bother you if Apple has been unreachable for 30+ min straight
            if not warned and time.time() - down_since > 1800:
                send(chat_id, f"⚠️ Apple's stock check has been failing for 30 min ({e}). "
                              f"I'll keep retrying and tell you when it's back.")
                warned = True
            time.sleep(min(300, 30 * fails))
            continue
        time.sleep(random.uniform(*POLL_SECONDS))
    log("Run window finished; next run takes over.")


if __name__ == "__main__":
    main()
