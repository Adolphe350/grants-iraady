#!/usr/bin/env python3
"""
scraper.py — In-container daily scraper for fundsforngospremium.com.

Runs INSIDE the grants-iraady container (Playwright + chromium are in the image).
Triggered two ways:
  - Dashboard "Run scraper" button  -> POST /api/run-scraper spawns this as a subprocess
  - APScheduler daily job (05:00 UTC) inside app.py

Design notes:
  - The FFN auth token lives only ~12 minutes, so every run does one fresh
    Playwright login. There is no way around a per-run login; the value is that
    OUR team never logs in to FFN — the bot does, and mirrors grants to our site.
  - Incremental by default: pages newest-first and STOPS once it reaches grants
    we already have, so a daily run only pulls what's genuinely new (fast, light).
  - mode=full re-pulls a large window to backfill.
  - Progress is written to the scrape_runs table so the dashboard can show live
    status. Grants are handed to the app's own /api/ingest endpoint (127.0.0.1),
    reusing all its enrichment + dedup logic.
"""

import os, sys, json, time, random, base64, sqlite3, logging, requests
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('scraper')

# ── Config (all overridable via env / Coolify) ───────────────────────────────
# FFN credentials are supplied via Coolify env vars (NOT hardcoded here — this
# file is in git). The scrape fails clearly if they are missing.
FFN_USER      = os.environ.get('FFN_USER',      '')
FFN_PASS      = os.environ.get('FFN_PASS',      '')
INGEST_URL    = os.environ.get('INGEST_URL',    'http://127.0.0.1:5000/api/ingest')
INGEST_SECRET = os.environ.get('INGEST_SECRET', 'uwezogrants2026')
DB_PATH       = os.environ.get('DB_PATH',       '/data/grants.db')
CORE_API      = 'https://core.fundsforngospremium.com/api'

MODE      = os.environ.get('SCRAPE_MODE',   'incremental')   # incremental | full
TRIGGER   = os.environ.get('SCRAPE_TRIGGER','manual')        # manual | scheduled
TARGET    = int(os.environ.get('SCRAPE_TARGET', '300'))      # cap for full mode
MAX_PAGES = int(os.environ.get('SCRAPE_MAX_PAGES', '25'))    # hard safety cap
RUN_ID    = None

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
]
ACCEPT_LANGUAGES = ['en-US,en;q=0.9', 'en-GB,en;q=0.9,en-US;q=0.8', 'en-US,en;q=0.9,fr;q=0.8', 'en-US,en;q=0.8']
VIEWPORTS = [
    {'width':1920,'height':1080},{'width':1440,'height':900},{'width':1366,'height':768},
    {'width':1536,'height':864},{'width':2560,'height':1440},
]

# ── scrape_runs status helpers ───────────────────────────────────────────────
def _db():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.execute("PRAGMA busy_timeout=30000")
    return c

def run_start():
    global RUN_ID
    try:
        c = _db()
        c.execute("""CREATE TABLE IF NOT EXISTS scrape_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP, status TEXT, trigger TEXT,
            fetched INTEGER DEFAULT 0, added INTEGER DEFAULT 0,
            message TEXT, pid INTEGER)""")
        cur = c.execute("INSERT INTO scrape_runs (status,trigger,message,pid) VALUES ('running',?,?,?)",
                        (TRIGGER, 'Starting…', os.getpid()))
        RUN_ID = cur.lastrowid
        c.commit(); c.close()
    except Exception as e:
        log.error(f"run_start failed: {e}")

def run_update(message=None, fetched=None, added=None):
    if RUN_ID is None: return
    try:
        c = _db()
        sets, vals = [], []
        if message is not None: sets.append("message=?"); vals.append(message)
        if fetched is not None: sets.append("fetched=?"); vals.append(fetched)
        if added   is not None: sets.append("added=?");   vals.append(added)
        if sets:
            vals.append(RUN_ID)
            c.execute("UPDATE scrape_runs SET " + ",".join(sets) + " WHERE id=?", vals)
            c.commit()
        c.close()
    except Exception as e:
        log.error(f"run_update failed: {e}")

def run_finish(status, message, fetched=0, added=0):
    if RUN_ID is None: return
    try:
        c = _db()
        c.execute("UPDATE scrape_runs SET status=?, message=?, fetched=?, added=?, finished_at=CURRENT_TIMESTAMP WHERE id=?",
                  (status, message, fetched, added, RUN_ID))
        c.commit(); c.close()
    except Exception as e:
        log.error(f"run_finish failed: {e}")

def existing_grant_ids():
    """Return the set of grant_id hashes already stored, to detect new grants."""
    try:
        c = _db()
        ids = {r[0] for r in c.execute("SELECT grant_id FROM grants").fetchall()}
        c.close()
        return ids
    except Exception:
        return set()

import hashlib
def grant_hash(g):
    return hashlib.md5((g.get('title','') + g.get('deadline','')).encode()).hexdigest()

# ── Human-like helpers ───────────────────────────────────────────────────────
def jitter(lo=1.0, hi=3.5):
    t = random.uniform(lo, hi); time.sleep(t); return t

def human_type(page, selector, text):
    page.click(selector)
    for ch in text:
        page.keyboard.type(ch); time.sleep(random.uniform(0.05, 0.18))

def random_scroll(page):
    for _ in range(random.randint(2,4)):
        page.mouse.wheel(0, random.randint(200,600)); time.sleep(random.uniform(0.3,0.8))
    time.sleep(random.uniform(0.5,1.2)); page.mouse.wheel(0, -random.randint(300,800))

def random_mouse_move(page):
    for _ in range(random.randint(2,5)):
        page.mouse.move(random.randint(100,1200), random.randint(100,700)); time.sleep(random.uniform(0.1,0.4))

# ── Auth ─────────────────────────────────────────────────────────────────────
def login_and_get_token():
    from playwright.sync_api import sync_playwright
    ua = random.choice(USER_AGENTS); viewport = random.choice(VIEWPORTS); accept_lang = random.choice(ACCEPT_LANGUAGES)
    log.info(f"Logging in | UA: {ua[:40]}... | viewport: {viewport}")
    result, token_captured = {}, []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage','--disable-blink-features=AutomationControlled'])
        ctx = browser.new_context(user_agent=ua, viewport=viewport, locale='en-US', timezone_id='Africa/Kigali',
            accept_downloads=False, extra_http_headers={'Accept-Language':accept_lang,'sec-ch-ua-platform':'"Windows"'})
        ctx.add_init_script("""
            Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
            Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
            Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
            window.chrome={runtime:{}};""")
        page = ctx.new_page()
        def on_request(req):
            auth = req.headers.get('authorization','')
            if auth.startswith('Bearer '):
                t = auth.replace('Bearer ','').strip()
                if t and t not in token_captured: token_captured.append(t)
        page.on('request', on_request)
        run_update(message="Logging in to Funds for NGOs…")
        page.goto('https://login.fundsforngospremium.com/', wait_until='domcontentloaded', timeout=25000)
        jitter(1.5,3.0); random_mouse_move(page); jitter(0.8,2.0)
        human_type(page, '#floatingInput', FFN_USER); jitter(0.5,1.5)
        human_type(page, '#floatingPassword', FFN_PASS); jitter(0.4,1.0)
        random_mouse_move(page); page.click('button[type=submit]')
        page.wait_for_load_state('domcontentloaded', timeout=15000); jitter(2.0,3.5)
        jitter(2.0,4.0); random_scroll(page); random_mouse_move(page); jitter(1.5,2.5)
        try:
            page.click('text=GRANTS', timeout=5000); jitter(2.0,4.0)
        except Exception:
            page.goto('https://grants.fundsforngospremium.com/', wait_until='domcontentloaded', timeout=25000); jitter(2.0,4.0)
        random_scroll(page); random_mouse_move(page); jitter(2.0,3.5)
        cookies = {c['name']:c['value'] for c in ctx.cookies()}
        result['token']               = token_captured[-1] if token_captured else None
        result['member_id']           = cookies.get('_USR_AUTH_','')
        result['access_token_cookie'] = cookies.get('_USR_ACCESSTOKEN_','')
        result['ua'] = ua; result['accept_lang'] = accept_lang
        browser.close()
    log.info("Token captured" if result.get('token') else "No Bearer token captured")
    return result

# ── Fetch ────────────────────────────────────────────────────────────────────
def make_api_headers(auth):
    token = auth.get('token') or auth.get('access_token_cookie','')
    return {
        'Accept':'application/json, text/plain, */*', 'Accept-Language':auth.get('accept_lang',ACCEPT_LANGUAGES[0]),
        'Content-Type':'application/json', 'Authorization':f'Bearer {token}', 'User-Agent':auth.get('ua',USER_AGENTS[0]),
        'Referer':'https://grants.fundsforngospremium.com/', 'Origin':'https://grants.fundsforngospremium.com',
        'sec-fetch-dest':'empty','sec-fetch-mode':'cors','sec-fetch-site':'same-site',
    }

def fetch_page(auth, page_index, page_size):
    payload = {'pageIndex':page_index,'pageSize':page_size,'userIp':'','memberId':auth.get('member_id',''),
               'platform':'NEW','viewType':'GLOBAL','countries':[],'issues':[],'toDate':None,'fromDate':None}
    r = requests.post(f'{CORE_API}/Grant/LatestSearch', json=payload, headers=make_api_headers(auth), timeout=30)
    if r.status_code != 200:
        log.error(f"LatestSearch page {page_index} -> {r.status_code}: {r.text[:150]}")
        return []
    return r.json().get('grants', [])

def fetch_grants(auth):
    """
    Page newest-first. In incremental mode, stop as soon as a whole page contains
    nothing new (we've caught up). In full mode, keep going up to TARGET. Does NOT
    rely on the API's totalCount (it reports 0 — the old early-break bug).
    """
    known = existing_grant_ids()
    log.info(f"{len(known)} grants already in DB | mode={MODE}")
    fetched, new_grants = [], []
    page_index, empty_streak = 1, 0
    while page_index <= MAX_PAGES:
        size = random.randint(12, 18)
        grants = fetch_page(auth, page_index, size)
        if not grants:
            empty_streak += 1
            if empty_streak >= 2: break
            page_index += 1; continue
        empty_streak = 0
        fetched.extend(grants)
        page_new = [g for g in grants if grant_hash(g) not in known]
        new_grants.extend(page_new)
        run_update(message=f"Scanned {len(fetched)} grants, {len(new_grants)} new so far…",
                   fetched=len(fetched), added=None)
        log.info(f"  page {page_index}: {len(grants)} grants, {len(page_new)} new")
        if MODE == 'incremental':
            if not page_new:            # whole page already known -> caught up
                break
        else:
            if len(fetched) >= TARGET:  # full backfill cap
                break
        page_index += 1
        time.sleep(random.uniform(3.0, 8.0))   # be gentle on their API
    return (new_grants if MODE == 'incremental' else fetched)

def normalize(raw):
    return {
        'title':raw.get('title',''), 'donorAgency':raw.get('donorAgency',''), 'grantSize':raw.get('grantSize',''),
        'category':raw.get('category','Grant'), 'posted':raw.get('posted',''), 'deadline':raw.get('deadline',''),
        'url':raw.get('url',''), 'image':raw.get('image',''),
        'description':raw.get('description') or raw.get('shortDescription') or '',
        'text':raw.get('fullText') or raw.get('text') or raw.get('content') or '',
        'applyLink':raw.get('applyLink') or raw.get('applicationUrl') or raw.get('websiteLink') or '',
    }

def post_to_ingest(grants):
    headers = {'Content-Type':'application/json','X-Secret':INGEST_SECRET}
    for attempt in range(3):
        try:
            r = requests.post(INGEST_URL, json={'grants':grants}, headers=headers, timeout=60)
            data = r.json() if 'json' in r.headers.get('content-type','') else {'raw':r.text}
            log.info(f"Ingest ({r.status_code}): {data}")
            return data
        except Exception as e:
            log.warning(f"Ingest attempt {attempt+1}/3 failed: {e}"); time.sleep(5)
    return {'error':'ingest failed'}

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    run_start()
    if os.environ.get('NO_JITTER') != '1' and TRIGGER == 'scheduled':
        s = random.uniform(0, 300); log.info(f"Startup jitter {s:.0f}s"); time.sleep(s)
    log.info(f"=== Scrape start {datetime.utcnow().isoformat()} trigger={TRIGGER} mode={MODE} ===")
    if not FFN_USER or not FFN_PASS:
        run_finish('failed', 'FFN_USER / FFN_PASS not configured (set them in Coolify env vars).')
        log.error("Missing FFN credentials"); sys.exit(1)
    try:
        auth = login_and_get_token()
        if not auth.get('token'):
            run_finish('failed', 'Login failed — no auth token (check FFN credentials).'); sys.exit(1)
        run_update(message="Logged in. Scanning latest grants…")
        grants = fetch_grants(auth)
        if not grants:
            run_finish('success', 'No new grants — already up to date.', fetched=0, added=0)
            log.info("No new grants."); return
        run_update(message=f"Saving {len(grants)} grants…", fetched=len(grants))
        result = post_to_ingest([normalize(g) for g in grants])
        added = result.get('added', 0) if isinstance(result, dict) else 0
        if isinstance(result, dict) and 'error' in result:
            run_finish('failed', f"Fetched {len(grants)} but ingest failed: {result['error']}", fetched=len(grants))
            sys.exit(1)
        msg = f"Done. {added} new grant(s) added" + (f", scanned {len(grants)}." if MODE=='incremental' else f" from {len(grants)} scanned.")
        run_finish('success', msg, fetched=len(grants), added=added)
        log.info("=== " + msg + " ===")
    except SystemExit:
        raise
    except Exception as e:
        log.exception("Scrape crashed")
        run_finish('failed', f"Error: {str(e)[:200]}")
        sys.exit(1)

if __name__ == '__main__':
    main()
