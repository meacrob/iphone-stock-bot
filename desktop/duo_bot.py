#!/usr/bin/env python3
"""
iPhone Duo 256GB - assisted checkout bot (Windows).

  python duo_bot.py login     -> opens the browser so you can sign in to Apple once
  python duo_bot.py practice  -> runs the checkout on whatever is in your bag NOW, stops at payment
  python duo_bot.py           -> watches TRX stock and runs the checkout the moment a Duo 256GB appears

It NEVER pays. It stops at the payment step, beeps, and pings you on Telegram.
"""

import configparser
import json
import os
import random
import re
import sys
import time
from datetime import datetime

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = configparser.ConfigParser()
CFG.read(os.path.join(HERE, "config.ini"), encoding="utf-8")
PROFILE_DIR = os.path.join(HERE, "apple-profile")
SHOTS = os.path.join(HERE, "screenshots")
STATE = os.path.join(HERE, "state.json")

BAG = "https://www.apple.com/my/shop/bag"
DUO_PAGE = "https://www.apple.com/my/shop/buy-iphone/iphone-duo"
RECS = "https://www.apple.com/my/shop/pickup-message-recommendations"
QUERY_PARTS = ["MK2E4X/A", "MK2K4X/A"]  # Duo 256GB Star White / Night Sky
WANT = ["Duo", "256GB"]                  # Apple's title must contain all of these
STORE = "The Exchange TRX"
POLL = (12, 18)                          # seconds between stock checks

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def cfg(section, key, default=""):
    try:
        return CFG.get(section, key).strip()
    except Exception:
        return default


def log(msg):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(os.path.join(HERE, "bot.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------- Windows helpers ----------------

def keep_awake():
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002)
    except Exception:
        pass


def beep(times=6):
    try:
        import winsound
        for _ in range(times):
            winsound.Beep(1800, 350)
            time.sleep(0.15)
    except Exception:
        print("\a" * times)


# ---------------- Telegram ----------------

def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return {}


def save_state(st):
    json.dump(st, open(STATE, "w", encoding="utf-8"))


def tg(method, **params):
    token = cfg("telegram", "token")
    if not token:
        return {}
    try:
        return requests.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=15).json()
    except Exception as e:
        log(f"telegram error: {e}")
        return {}


def chat_id():
    st = load_state()
    if st.get("chat_id"):
        return st["chat_id"]
    for u in reversed(tg("getUpdates").get("result", [])):
        msg = u.get("message") or u.get("edited_message")
        if msg:
            st["chat_id"] = msg["chat"]["id"]
            save_state(st)
            return st["chat_id"]
    return None


def ping(text):
    cid = chat_id()
    if cid:
        tg("sendMessage", chat_id=cid, text=text, disable_web_page_preview=True)
    log("TELEGRAM: " + text.replace("\n", " | "))


# ---------------- Stock watching ----------------

class Watcher:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "en-MY,en;q=0.9", "Referer": DUO_PAGE})
        try:
            self.s.get(DUO_PAGE, timeout=20)
        except Exception:
            pass
        self.n = 0

    def check(self):
        """Returns (title, quote) of an available Duo 256GB at TRX, or None."""
        part = QUERY_PARTS[self.n % len(QUERY_PARTS)]
        self.n += 1
        r = self.s.get(RECS, params={"mts.0": "regular", "mts.1": "compact", "location": cfg("pickup", "postcode", "55188"),
                                     "product": part}, timeout=20)
        r.raise_for_status()
        pm = (r.json().get("body") or {}).get("PickupMessage") or {}
        for st in pm.get("stores", []):
            if STORE.lower() not in st.get("storeName", "").lower():
                continue
            for pn, info in (st.get("partsAvailability") or {}).items():
                title = (((info.get("messageTypes") or {}).get("regular") or {})
                         .get("storePickupProductTitle", pn)).replace(" ", " ")
                if info.get("pickupDisplay") == "available" and all(w in title for w in WANT):
                    return title, info.get("pickupSearchQuote", "")
        return None


# ---------------- Browser automation ----------------

def shot(page, name):
    os.makedirs(SHOTS, exist_ok=True)
    try:
        page.screenshot(path=os.path.join(SHOTS, f"{datetime.now():%m%d-%H%M%S}-{name}.png"), full_page=False)
    except Exception:
        pass


def first_visible(page, candidates, timeout=8):
    """candidates: list of functions page -> locator. Returns the first that becomes visible."""
    end = time.time() + timeout
    while time.time() < end:
        for make in candidates:
            try:
                loc = make(page).first
                if loc.is_visible():
                    return loc
            except Exception:
                pass
        time.sleep(0.25)
    return None


def click(page, step, candidates, timeout=10):
    loc = first_visible(page, candidates, timeout)
    if not loc:
        raise StepFailed(step)
    loc.scroll_into_view_if_needed()
    loc.click()
    log(f"clicked: {step}")
    return loc


class StepFailed(Exception):
    pass


def btn(pattern):
    return lambda p: p.get_by_role("button", name=re.compile(pattern, re.I))


def css(sel):
    return lambda p: p.locator(sel)


def text(pattern):
    return lambda p: p.get_by_text(re.compile(pattern, re.I))


def prune_bag(page, keep_title):
    """Move every bag item that isn't the in-stock model out of the bag (pickup needs all items available).
    Uses 'Save for later' so you can put it back with one tap; falls back to Remove."""
    for _ in range(4):
        removed = page.evaluate(
            """(keep) => {
                const all = [...document.querySelectorAll('button, a')];
                const label = b => (b.innerText || b.getAttribute('aria-label') || '');
                let btns = all.filter(b => /save for later/i.test(label(b)));
                if (!btns.length) btns = all.filter(b => /^\\s*remove/i.test(label(b)));
                for (const b of btns) {
                    let el = b;
                    for (let i = 0; i < 12 && el; i++) {
                        el = el.parentElement;
                        if (el && /iPhone/.test(el.innerText) && el.innerText.length < 4000) break;
                    }
                    const t = (el ? el.innerText : '').replace(/\\u00a0/g, ' ');
                    if (!t.includes(keep)) { b.click(); return t.split('\\n')[0]; }
                }
                return null;
            }""", keep_title)
        if not removed:
            return
        log(f"removed from bag: {removed}")
        page.wait_for_timeout(2500)


def fill_if_empty(page, label_pattern, value):
    if not value:
        return
    try:
        loc = page.get_by_label(re.compile(label_pattern, re.I)).first
        if loc.is_visible() and not loc.input_value():
            loc.fill(value)
            log(f"filled: {label_pattern}")
    except Exception:
        pass


def fill_any(page, selectors, labels, value, name):
    """Fill the first matching empty field in the page or any iframe (card fields are often in iframes)."""
    if not value:
        return False
    for fr in page.frames:
        cands = [fr.locator(s) for s in selectors] + [fr.get_by_label(re.compile(labels, re.I)),
                                                       fr.get_by_placeholder(re.compile(labels, re.I))]
        for loc in cands:
            try:
                loc = loc.first
                if loc.is_visible() and not loc.input_value():
                    loc.fill(value)
                    log(f"filled: {name}")
                    return True
            except Exception:
                pass
    return False


def fill_card(page):
    """Choose card payment, fill the card from config.ini, go to Review. Never clicks Place Order."""
    num = cfg("card", "number").replace(" ", "")
    if not num:
        return False
    first_visible(page, [text(r"credit or debit card")], timeout=3) and \
        click(page, "Card option", [css('[data-autom*="credit" i]'), lambda p: p.get_by_label(re.compile(r"credit or debit card", re.I)),
                                    text(r"credit or debit card")], timeout=5)
    page.wait_for_timeout(1200)
    fill_any(page, ['input[autocomplete="cc-number"]', 'input[name*="cardNumber" i]'], r"card number", num, "card number")
    exp = cfg("card", "expiry")  # MM/YY
    fill_any(page, ['input[autocomplete="cc-exp"]', 'input[name*="expiration" i]'], r"expir|MM ?/ ?YY", exp, "expiry")
    fill_any(page, ['input[autocomplete="cc-csc"]', 'input[name*="security" i]', 'input[name*="cvv" i]'],
             r"cvv|cvc|security code", cfg("card", "cvv"), "cvv")
    fill_any(page, ['input[autocomplete="cc-name"]'], r"name on card|cardholder", cfg("card", "name_on_card"), "name on card")
    shot(page, "6-card")
    click(page, "Review order", [css('[data-autom="continue-button-label"]'), btn(r"review (your )?order"),
                                 btn(r"continue to review"), btn(r"^\s*continue\s*$")], timeout=10)
    page.wait_for_timeout(2000)
    shot(page, "7-review")
    return bool(first_visible(page, [btn(r"place (your )?order")], timeout=8))


def on_payment_page(page):
    return bool(first_visible(page, [text(r"how (would|do) you (like to )?pay"), text(r"payment method"),
                                     text(r"credit or debit card")], timeout=1))


def checkout(page, keep_title=None):
    """Bag -> Check Out -> pickup at TRX -> pickup details -> stop at payment. Returns True if at payment."""
    t0 = time.time()
    page.goto(BAG, wait_until="domcontentloaded")
    page.bring_to_front()
    shot(page, "1-bag")
    if keep_title:
        prune_bag(page, keep_title)

    click(page, "Check Out", [css('[data-autom="checkout"]'), css('button[id*="checkout" i]'),
                              btn(r"^\s*check\s*out\s*$"), btn(r"check\s*out")], timeout=15)
    page.wait_for_load_state("domcontentloaded")
    shot(page, "2-after-checkout")

    # Apple may ask you to sign in again at checkout
    if first_visible(page, [css('input[type="password"]'), text(r"sign in to apple store|sign in for faster checkout")], timeout=2):
        ping("🔐 Apple wants you to sign in at checkout. Go to the PC and sign in NOW. I'll carry on after.")
        beep(4)
        if not first_visible(page, [btn(r"pick (it )?up|pickup"), text(r"how would you like to get")], timeout=180):
            raise StepFailed("sign in")

    click(page, "Pickup option", [css('[data-autom="fulfillment-pickup-button"]'), btn(r"i.?ll pick (it )?up"),
                                  text(r"i.?ll pick (it )?up"), btn(r"^\s*pick\s*up\s*$")], timeout=20)
    page.wait_for_timeout(1200)

    # Store search box (sometimes shown, sometimes prefilled)
    box = first_visible(page, [css('input[data-autom*="zip" i]'), css('input[id*="storeLocator" i]'),
                               lambda p: p.get_by_placeholder(re.compile(r"postcode|location|zip", re.I))], timeout=3)
    if box:
        box.fill(cfg("pickup", "postcode", "55188"))
        box.press("Enter")
        page.wait_for_timeout(2000)

    click(page, "Store TRX", [lambda p: p.get_by_label(re.compile(STORE, re.I)), text(STORE)], timeout=15)
    page.wait_for_timeout(1500)
    shot(page, "3-store")

    # Pickup time: pick the first available slot if Apple asks
    try:
        sel = page.locator("select").filter(has=page.locator("option")).first
        if sel.is_visible():
            opts = sel.locator("option").all()
            for o in opts:
                v = o.get_attribute("value")
                if v and not o.is_disabled():
                    sel.select_option(v)
                    log("picked first time slot")
                    break
    except Exception:
        pass
    slot = first_visible(page, [css('[data-autom*="timeslot" i] input'), css('input[name*="timeSlot" i]')], timeout=1)
    if slot:
        slot.check(force=True)

    click(page, "Continue (pickup)", [css('[data-autom="fulfillment-continue-button"]'),
                                       btn(r"continue to pickup details"), btn(r"^\s*continue\s*$")], timeout=15)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)
    shot(page, "4-pickup-details")

    if not on_payment_page(page):
        fill_if_empty(page, r"first name", cfg("pickup", "first_name"))
        fill_if_empty(page, r"last name", cfg("pickup", "last_name"))
        fill_if_empty(page, r"email", cfg("pickup", "email"))
        fill_if_empty(page, r"phone|mobile", cfg("pickup", "phone"))
        fill_if_empty(page, r"\bic\b|identification|mykad|nric", cfg("pickup", "ic_number"))
        fill_if_empty(page, r"\btin\b|tax identification", cfg("pickup", "tin"))
        click(page, "Continue (to payment)", [css('[data-autom="pickup-continue-button"]'),
                                               btn(r"continue to payment"), btn(r"^\s*continue\s*$")], timeout=15)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1500)

    shot(page, "5-payment")
    ok = on_payment_page(page)
    if ok and cfg("card", "number"):
        try:
            if fill_card(page):
                log(f"checkout reached REVIEW (Place Order) in {time.time() - t0:.0f}s")
                return "review", time.time() - t0
        except StepFailed as e:
            log(f"card step stuck at {e}; leaving it on payment")
    log(f"checkout reached {'PAYMENT' if ok else 'unknown page'} in {time.time() - t0:.0f}s")
    return ok, time.time() - t0


def open_browser(pw):
    args = dict(user_data_dir=PROFILE_DIR, headless=False, viewport={"width": 1280, "height": 900},
                locale="en-MY", args=["--disable-blink-features=AutomationControlled"])
    try:
        return pw.chromium.launch_persistent_context(channel="chrome", **args)  # your real Chrome
    except Exception:
        return pw.chromium.launch_persistent_context(**args)


def run_checkout(page, keep_title, label):
    try:
        ok, secs = checkout(page, keep_title)
        beep(8)
        if ok == "review":
            ping(f"💳 PLACE ORDER NOW - {label}\nCard is filled, bot is on the final screen ({secs:.0f}s).\n"
                 f"Go to the PC, tap Place Order, then approve the OTP / bank app.")
        elif ok:
            ping(f"💳 PAY NOW - {label}\nBot reached the payment step in {secs:.0f}s.\n"
                 f"Go to the PC, pick your card, enter the OTP and place the order.")
        else:
            ping(f"⚠️ {label}\nBot finished its steps but isn't sure it's on payment. Check the PC NOW and finish manually.")
    except StepFailed as e:
        shot(page, f"stuck-{e}")
        beep(8)
        ping(f"⚠️ {label}\nBot got stuck at: {e}. Finish manually on the PC NOW (bag is open).")
    except Exception as e:
        shot(page, "error")
        beep(8)
        ping(f"⚠️ {label}\nBot error: {e}. Finish manually on the PC NOW.")


# ---------------- Modes ----------------

def mode_login():
    with sync_playwright() as pw:
        ctx = open_browser(pw)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.apple.com/my/shop/bag")
        print("\n>>> Sign in to your Apple ID in this window (Bag > Sign in), tick 'Remember me'.")
        print(">>> Make sure your bag has ONLY: iPhone Duo 256GB Night Sky + iPhone Duo 256GB Star White.")
        input(">>> When done, come back here and press Enter to save and close... ")
        ctx.close()
    chat_id()
    print("Saved. Now run practice.bat once, then start.bat.")


def mode_practice():
    keep_awake()
    with sync_playwright() as pw:
        ctx = open_browser(pw)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        ping("🧪 Practice run starting (no purchase, stops at payment).")
        run_checkout(page, None, "PRACTICE")
        input("\n>>> Practice done. Look at the browser, then press Enter to close (nothing is bought)... ")
        ctx.close()


def mode_watch():
    keep_awake()
    w = Watcher()
    with sync_playwright() as pw:
        ctx = open_browser(pw)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(BAG, wait_until="domcontentloaded")
        ping("🤖 Auto-checkout bot is ON (PC). Watching iPhone Duo 256GB at TRX every ~15s.")
        fails, cooldown_until, last_refresh = 0, 0, time.time()
        while True:
            try:
                hit = w.check() if time.time() > cooldown_until else None
                fails = 0
                if hit:
                    title, quote = hit
                    log(f"HIT: {title} - {quote}")
                    ping(f"🚨 {title} at TRX ({quote}). Bot is checking out NOW...")
                    run_checkout(page, title, title)
                    cooldown_until = time.time() + 15 * 60  # don't restart checkout while you're paying
                else:
                    log("no stock")
                # keep the Apple session warm so checkout doesn't ask you to sign in
                if time.time() - last_refresh > 20 * 60 and time.time() > cooldown_until:
                    page.goto(BAG, wait_until="domcontentloaded")
                    last_refresh = time.time()
            except Exception as e:
                fails += 1
                log(f"check failed ({fails}): {e}")
                if fails == 1:
                    w = Watcher()
                time.sleep(min(120, 10 * fails))
                continue
            time.sleep(random.uniform(*POLL))


if __name__ == "__main__":
    mode = (sys.argv[1] if len(sys.argv) > 1 else "watch").lower()
    {"login": mode_login, "practice": mode_practice}.get(mode, mode_watch)()
