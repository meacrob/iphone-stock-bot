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

PINNED_PART = "MJXQ4X/A"  # iPhone 18 Pro Max 256GB Burgundy (MY)


def discover_part():
    """Find the MY part number for Pro Max 256GB Burgundy."""
    return PINNED_PART
    try:
        html = s.get(PRODUCT_PAGE, timeout=20).text
        for m in re.finditer(r'"partNumber"\s*:\s*"([A-Z0-9]{4,6}[A-Z]{1,2}/A)"', html):
            w = html[max(0, m.start() - 900): m.end() + 900].lower()
            if COLOR in w and CAPACITY in w and ("6_9inch" in w or "pro max" in w or "promax" in w):
                return m.group(1)
    except Exception as e:
        log(f"page scrape failed: {e}")
    # Fallback: ask the endpoint which guess it recognises
    for p in FALLBACK_PARTS:
        try:
            stores = fetch([p])
            if any(p in (st.get("partsAvailability") or {}) for st in stores):
                return p
        except Exception:
            pass
    return None


def fetch(parts):
    params = {"fae": "true", "pl": "true", "mts.0": "regular", "location": POSTCODE}
    for i, p in enumerate(parts):
        params[f"parts.{i}"] = p
    r = s.get(FULFILLMENT, params=params, timeout=20)
    r.raise_for_status()
    return r.json()["body"]["content"]["pickupMessage"].get("stores", [])


# ---------------- Main loop ----------------

def main():
    chat_id, first_time = get_chat_id()
    part = discover_part()
    if not part:
        send(chat_id, "⚠️ Tracker couldn't find the part number for Pro Max 256GB Burgundy. Ask Claude to check.")
        sys.exit("part number not found")
    log(f"Tracking {part}")
    title = part
    try:
        for st in fetch([part]):
            info = (st.get("partsAvailability") or {}).get(part)
            if info:
                title = (info.get("messageTypes", {}).get("regular", {}) or {}).get("storePickupProductTitle", part)
                break
    except Exception as e:
        log(f"title lookup failed: {e}")
    log(f"Apple says this part is: {title}")
    if first_time or os.environ.get("ANNOUNCE") == "1":
        send(chat_id, f"✅ Tracker is live\nApple product: {title}\nPart: {part}\n"
                      f"Checking Apple TRX + Bukit Jalil every ~1 min. I'll message you the second it's available for pickup.")

    end = time.time() + RUN_MINUTES * 60
    alerted, fails = set(), 0
    while time.time() < end:
        try:
            stores = fetch([part])
            fails = 0
            available = set()
            for st in stores:
                info = (st.get("partsAvailability") or {}).get(part)
                if not info:
                    continue
                name = st.get("storeName", "?")
                status = info.get("pickupDisplay")
                quote = info.get("pickupSearchQuote", "")
                log(f"{name}: {status} | {quote}")
                if status == "available":
                    available.add(name)
                    if name not in alerted:
                        send(chat_id, f"🚨 IN STOCK NOW\niPhone 18 Pro Max 256GB Burgundy\n"
                                      f"📍 Apple {name}\n🕒 {quote}\n\nBuy now 👉 {PRODUCT_PAGE}")
                        alerted.add(name)
            alerted &= available  # re-alert if it sells out and comes back
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
