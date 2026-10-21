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
import threading
import time
from datetime import datetime, timedelta, timezone

import requests

TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
CHAT_FILE = "state/chat_id.txt"
RUN_MINUTES = int(os.environ.get("RUN_MINUTES", "340"))
POLL_SECONDS = (17, 23)  # ~every 20s; 1 request per check keeps Apple load the same as before
POSTCODE = "55188"  # KL (Apple The Exchange TRX)
MYT = timezone(timedelta(hours=8))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

# ---------------- What to watch ----------------
# A model matches if Apple's product title contains ALL words in "match".
TARGETS = [
    {"name": "iPhone Duo 256GB",
     "match": ["Duo", "256GB"],
     "url": "https://www.apple.com/my/shop/buy-iphone/iphone-duo"},
    {"name": "iPhone Duo 512GB",
     "match": ["Duo", "512GB"],
     "url": "https://www.apple.com/my/shop/buy-iphone/iphone-duo"},
    {"name": "iPhone Duo 1TB",
     "match": ["Duo", "1TB"],
     "url": "https://www.apple.com/my/shop/buy-iphone/iphone-duo"},
]
# Apple's feed returns every available model in the same family, so one part
# per family is enough. Every round also checks one extra part in rotation as backup.
MAIN_QUERIES = ["MK2E4X/A", "MK2K4X/A"]    # Duo 256 Star White, Duo 256 Night Sky
EXTRA_QUERIES = ["MK2G4X/A", "MK2D4X/A",  # Duo 512 Star White, Duo 512 Night Sky
                 "MK2H4X/A", "MK2F4X/A"]  # Duo 1TB Star White, Duo 1TB Night Sky
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
        """Returns ({(store, model title): (quote, url)}, number of models seen)."""
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
                            hits[(store, title)] = (info.get("pickupSearchQuote", ""), t["url"])
            if len(queries) > 1:
                time.sleep(random.uniform(2, 5))
        if ok == 0:
            raise RuntimeError(f"Apple returned {last}")
        return hits, seen


# ---------------- Stock window tracking ----------------

LIVE_FILE = "state/live.json"


def hhmm(ts):
    return datetime.fromtimestamp(ts, MYT).strftime("%I:%M %p").lstrip("0")


def load_live():
    try:
        import json
        return json.load(open(LIVE_FILE))
    except Exception:
        return {}


def save_live(live):
    import json
    os.makedirs("state", exist_ok=True)
    json.dump(live, open(LIVE_FILE, "w"))


def follow_up_pings(chat_id):
    for n in (2, 3):  # extra pings so you don't sleep through it
        time.sleep(10)
        send(chat_id, f"⏰ ({n}/3) DUO IN STOCK - go go go 👉 https://www.apple.com/my/shop/bag")


def gone_alert(chat_id, k, v):
    store, title = k.split("|", 1)
    mins = max(1, round((v["last"] - v["first"]) / 60))
    send(chat_id, f"❌ GONE - no longer available for pickup\n{title}\n📍 Apple {store}\n"
                  f"🕒 Available {hhmm(v['first'])} to about {hhmm(v['last'])} (~{mins} min)")


# ---------------- Main loop ----------------

def main():
    chat_id, first_time = get_chat_id()
    apple = Apple()
    watching = "\n".join(f"- {t['name']}" for t in TARGETS)
    if first_time or os.environ.get("ANNOUNCE") == "1":
        send(chat_id, f"✅ Tracker updated\nWatching at Apple TRX (every ~20 sec):\n{watching}\n\n"
                      f"I'll message you the moment any of these is available for pickup.")

    end = time.time() + RUN_MINUTES * 60
    fails, down_since, warned, rnd = 0, None, False, 0
    live = load_live()   # {"store|title": {"first": ts, "last": ts, "miss": n}}
    # Anything carried over from the previous run that went stale: report it gone
    for k, v in list(live.items()):
        if time.time() - v["last"] > 600:
            gone_alert(chat_id, k, v)
            live.pop(k)
    while time.time() < end:
        rnd += 1
        allq = MAIN_QUERIES + EXTRA_QUERIES
        queries = [allq[rnd % len(allq)]]  # one Duo part per check; Apple returns the whole Duo family
        try:
            if time.time() - apple.born > 1800:
                apple.new_session()
            hits, seen = apple.check(queries)
            if warned:
                send(chat_id, "✅ Apple is responding again, tracking resumed.")
            fails, down_since, warned = 0, None, False
            now = time.time()
            log(f"ok | seen={seen} | hits={list(hits)}")
            for (store, title), (quote, url) in hits.items():
                k = f"{store}|{title}"
                if k in live:
                    live[k]["last"], live[k]["miss"] = now, 0
                    continue
                live[k] = {"first": now, "last": now, "miss": 0}
                send(chat_id, f"🚨🚨 IN STOCK NOW 🚨🚨\n{title} - {quote}\n📍 Apple {store}\n"
                              f"🕒 Spotted at {hhmm(now)}\n\n"
                              f"🛍 Checkout 👉 https://www.apple.com/my/shop/bag\n"
                              f"🔗 Not in bag? Product page 👉 {url}")
                threading.Thread(target=follow_up_pings, args=(chat_id,), daemon=True).start()
            # Not seen this round: needs 2 misses in a row before we call it gone (avoids blips)
            current = {f"{s}|{ti}" for s, ti in hits}
            for k in list(live):
                if k in current:
                    continue
                live[k]["miss"] += 1
                if live[k]["miss"] >= 3:
                    gone_alert(chat_id, k, live.pop(k))
            save_live(live)
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
