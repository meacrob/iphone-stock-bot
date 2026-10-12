#!/usr/bin/env python3
"""
iPhone 18 Pro Max 256GB Burgundy - Apple Store Malaysia pickup tracker.

Runs inside GitHub Actions. Checks Apple's pickup availability for the
Malaysian stores roughly every minute and messages you on Telegram the
moment it shows "available".

Secrets/env:
  TELEGRAM_TOKEN    bot token from @BotFather (required)
  TELEGRAM_CHAT_ID  optional; auto-detected from the last chat with the bot
  RUN_MINUTES       how long one run loops before exiting (default 340)
"""

import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
CHAT_FILE = "state/chat_id.txt"
RUN_MINUTES = int(os.environ.get("RUN_MINUTES", "340"))
POLL_SECONDS = (50, 70)

POSTCODE = "55188"  # KL; Apple returns nearby stores (TRX, Bukit Jalil)
COLOR, CAPACITY = "burgundy", "256gb"
PRODUCT_PAGE = "https://www.apple.com/my/shop/buy-iphone/iphone-18-pro"
FULFILLMENT = "https://www.apple.com/my/shop/fulfillment-messages"
# Fallback guesses if page scraping fails (EU code is MJXQ4HX/A; region suffix differs)
FALLBACK_PARTS = ["MJXQ4ZP/A", "MJXQ4MY/A", "MJXQ4X/A", "MJXQ4PP/A"]

MYT = timezone(timedelta(hours=8))
s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Accept-Language": "en-MY,en;q=0.9",
    "Referer": PRODUCT_PAGE,
})


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
    me = tg("getMe")
    print("getMe:", "ok @" + me["result"]["username"] if me.get("ok") else me, flush=True)
    resp = tg("getUpdates")
    print("getUpdates:", resp.get("ok"), "count", len(resp.get("result", [])), resp.get("description", ""), flush=True)
    upd = resp.get("result", [])
    for u in reversed(upd):
        msg = u.get("message") or u.get("edited_message")
        if msg:
            cid = str(msg["chat"]["id"])
            os.makedirs("state", exist_ok=True)
            open(CHAT_FILE, "w").write(cid)
            return cid, True
    sys.exit("No chat found. Open your bot on Telegram and send it any message, then re-run.")


def send(chat_id, text):
    try:
        tg("sendMessage", chat_id=chat_id, text=text, disable_web_page_preview=True)
    except Exception as e:
        log(f"telegram failed: {e}")


# ---------------- Apple ----------------

# What to watch: Apple's product title -> part number + buy link
TARGETS = {
    "iPhone 18 Pro Max 256GB Burgundy": ("MJXQ4X/A", "https://www.apple.com/my/shop/buy-iphone/iphone-18-pro/6.9-inch-display-256gb-burgundy"),
    "iPhone 18 Pro Max 512GB Burgundy": ("MJXV4X/A", "https://www.apple.com/my/shop/buy-iphone/iphone-18-pro/6.9-inch-display-512gb-burgundy"),
}
RECS = "https://www.apple.com/my/shop/pickup-message-recommendations"
TEST_MATCH = os.environ.get("TEST_MATCH", "")
# Query each target part plus a sibling (256GB black) so targets show up either way
QUERY_PRODUCTS = (os.environ.get("TEST_QUERY") or ",".join([p for p, _ in TARGETS.values()] + ["MJXN4X/A"])).split(",")
WARM_URL = next(iter(TARGETS.values()))[1]
NAMES = " + ".join(t.replace("iPhone 18 Pro Max ", "") for t in TARGETS)


def warm():
    s.headers["Referer"] = WARM_URL
    s.get(WARM_URL, timeout=20)


def check_once():
    """Returns ({(store, title): (quote, url)} for targets available, set of everything seen)."""
    hits, seen, ok, r = {}, set(), 0, None
    parts = {p: t for t, (p, _) in TARGETS.items()}
    for prod in QUERY_PRODUCTS:
        r = s.get(RECS, params={"mts.0": "regular", "mts.1": "compact", "location": POSTCODE, "product": prod}, timeout=20)
        if r.status_code != 200 or not r.text.lstrip().startswith("{"):
            continue
        ok += 1
        pm = (r.json().get("body") or {}).get("PickupMessage") or {}
        for st in pm.get("stores", []):
            name = st.get("storeName", "?")
            for pn, info in (st.get("partsAvailability") or {}).items():
                title = ((info.get("messageTypes") or {}).get("regular") or {}).get("storePickupProductTitle", pn).replace("\u00a0", " ")
                quote = info.get("pickupSearchQuote", "")
                seen.add(f"{title} @ {name}: {quote}")
                if info.get("pickupDisplay") != "available":
                    continue
                if TEST_MATCH:
                    if TEST_MATCH in title:
                        hits[(name, title)] = (quote, WARM_URL)
                    continue
                target = parts.get(pn) or next((t for t in TARGETS if t in title), None)
                if target:
                    hits[(name, target)] = (quote, TARGETS[target][1])
    if ok == 0:
        raise RuntimeError(f"Apple returned {getattr(r, 'status_code', '?')}")
    return hits, seen


# ---------------- Main loop ----------------

def main():
    chat_id, first_time = get_chat_id()
    warm()
    hits, seen = check_once()
    log(f"First check OK. Seen: {seen or 'nothing nearby'}")
    if TEST_MATCH:
        for x in sorted(seen): print("::notice::" + x, flush=True)
    if first_time or os.environ.get("ANNOUNCE") == "1":
        now = ", ".join(f"{t.replace('iPhone 18 Pro Max ', '')}" for (_, t) in hits) or "nothing yet"
        send(chat_id, f"✅ Tracker updated\niPhone 18 Pro Max Burgundy: {NAMES}\n"
                      f"Checking Apple TRX every ~1 min. I'll message you the second either is available for pickup.\n\n"
                      f"Available right now: {now}")

    end = time.time() + RUN_MINUTES * 60
    alerted, fails = set(), 0
    last_warm = time.time()
    while time.time() < end:
        try:
            if time.time() - last_warm > 1800:
                warm(); last_warm = time.time()
            hits, seen = check_once()
            fails = 0
            log(f"hits={list(hits)} | seen={len(seen)}")
            for (name, title), (quote, url) in hits.items():
                if (name, title) not in alerted:
                    prefix = f"🧪 TEST ALERT (matched '{TEST_MATCH}'), ignore\n" if TEST_MATCH else ""
                    send(chat_id, f"{prefix}🚨 IN STOCK NOW\n{title}\n📍 Apple {name}\n🕒 {quote}\n\nBuy now 👉 {url}")
                    alerted.add((name, title))
            alerted &= set(hits)  # re-alert if it sells out and comes back
        except Exception as e:
            fails += 1
            log(f"check failed ({fails}): {e}")
            if fails == 15:
                send(chat_id, f"⚠️ Tracker having trouble reaching Apple: {e}")
            time.sleep(min(300, 20 * fails))
            continue
        time.sleep(random.uniform(*POLL_SECONDS))
    log("Run window finished; next scheduled run takes over.")


if __name__ == "__main__":
    main()
