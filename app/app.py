import os, sys, sqlite3, hashlib, re, subprocess, fcntl, atexit
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, jsonify, request, session, redirect, url_for, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder='/app/static')
app.secret_key = os.environ.get('SECRET_KEY', 'grants-hub-secret-2026')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
CORS(app)

SITE_PASSWORD = os.environ.get('SITE_PASSWORD', 'Kigali2020@')
DB_PATH = os.environ.get('GRANTS_DB_PATH', '/data/grants.db')   # env override is for local tests only
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')   # == /app/static in the container

REGIONS = ['Africa','Asia','Asia-Pacific','Americas','Caribbean','Central America','Central Asia',
           'Central Europe','Eastern Africa','Eastern Europe','Global','Latin America','Middle East',
           'North Africa','North America','Oceania','Pacific','South America','South Asia',
           'Southeast Asia','Southern Africa','Sub-Saharan Africa','West Africa','Western Europe']

def detect_region(text):
    if not text: return 'Global'
    t = text.lower()
    for r in REGIONS:
        if r.lower() in t: return r
    country_map = {
        'Africa': ['rwanda','kenya','nigeria','ghana','ethiopia','tanzania','uganda','zambia','malawi',
                   'mozambique','cameroon','senegal','mali','niger','chad','sudan','angola','zimbabwe',
                   'botswana','namibia','lesotho','eswatini','south africa','egypt','morocco','tunisia','algeria'],
        'Asia':   ['india','china','bangladesh','pakistan','nepal','sri lanka','myanmar','vietnam',
                   'thailand','indonesia','philippines','cambodia','laos','malaysia'],
        'Americas':['united states','usa','canada','brazil','mexico','colombia','peru','chile','argentina'],
        'Europe': ['europe','european','uk','united kingdom','france','germany','spain','italy','netherlands','sweden'],
    }
    for region, countries in country_map.items():
        for c in countries:
            if c in t: return region
    return 'Global'

def detect_eligible_org(text):
    if not text: return ''
    t = text.lower()
    types = []
    if any(w in t for w in ['ngo','non-governmental','civil society','nonprofit','non-profit']): types.append('NGO')
    if any(w in t for w in ['university','academic','research institution','college','institute']): types.append('Academic')
    if any(w in t for w in ['company','business','enterprise','startup','sme','corporation','private sector']): types.append('Private Sector')
    if any(w in t for w in ['government','government agency','public sector','municipality']): types.append('Government')
    if any(w in t for w in ['individual','person','citizen','student','researcher','artist']): types.append('Individual')
    return ', '.join(types) if types else 'NGO'

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    conn = get_db()
    try:
        conn.execute("PRAGMA journal_mode=WAL")   # fewer writer/reader locks (scraper + web share the DB)
    except Exception:
        pass
    conn.execute("""CREATE TABLE IF NOT EXISTS grants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grant_id TEXT UNIQUE, title TEXT, donor TEXT,
        grant_size TEXT, category TEXT, posted_date TEXT,
        deadline TEXT, deadline_iso TEXT, url TEXT, image TEXT,
        slug TEXT, description TEXT, full_text TEXT, apply_url TEXT,
        region TEXT, eligible_org TEXT, status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS scrape_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMP, status TEXT, trigger TEXT,
        fetched INTEGER DEFAULT 0, added INTEGER DEFAULT 0,
        message TEXT, pid INTEGER
    )""")
    for col in ['deadline_iso','slug','description','full_text','apply_url','region','eligible_org','status','countries']:
        try:
            conn.execute("ALTER TABLE grants ADD COLUMN " + col + " TEXT")
        except Exception:
            pass
    conn.commit()

    today_iso = datetime.utcnow().strftime("%Y-%m-%d")

    # Backfill region/eligible_org/status for rows missing them
    rows = conn.execute(
        "SELECT id, deadline, url, full_text, description, deadline_iso FROM grants WHERE region IS NULL OR region=''"
    ).fetchall()
    for row in rows:
        text = (row[3] or '') + ' ' + (row[4] or '')
        slug = row[2].split('/op/')[-1] if '/op/' in (row[2] or '') else ''
        deadline_iso = row[5] or ''
        if not deadline_iso:
            try:
                deadline_iso = datetime.strptime(row[1], "%B %d, %Y").strftime("%Y-%m-%d")
            except Exception:
                pass
        region   = detect_region(text)
        eligible = detect_eligible_org(text)
        status   = 'expired' if (deadline_iso and deadline_iso < today_iso) else 'active'
        conn.execute(
            "UPDATE grants SET region=?, eligible_org=?, deadline_iso=COALESCE(NULLIF(deadline_iso,''),?), slug=COALESCE(NULLIF(slug,''),?), status=? WHERE id=?",
            (region, eligible, deadline_iso, slug, status, row[0])
        )

    # Every startup: move any grants whose deadline has now passed to 'expired'
    conn.execute(
        "UPDATE grants SET status='expired' WHERE deadline_iso IS NOT NULL AND deadline_iso != '' AND deadline_iso < ? AND (status IS NULL OR status != 'expired')",
        (today_iso,)
    )
    # Ensure no nulls
    conn.execute("UPDATE grants SET status='active' WHERE status IS NULL OR status = ''")
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            if request.path.startswith('/api/'): return jsonify({'error':'Unauthorized'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET','POST'])
def login_page():
    error = False
    if request.method == 'POST':
        if request.form.get('password') == SITE_PASSWORD:
            session.permanent = True
            session['authenticated'] = True
            return redirect(url_for('index'))
        error = True
    html = open('/app/static/login.html').read()
    if error: html = html.replace('<!--ERROR-->', '<div class="error">Incorrect password. Try again.</div>')
    return html, 200, {'Content-Type': 'text/html'}

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/healthz')
def healthz():
    return jsonify({'ok': True}), 200

# Public (no login) — required by Google Play's account-deletion policy.
@app.route('/account-deletion')
def account_deletion():
    return send_file('/app/static/account-deletion.html')

@app.route('/')
@login_required
def index(): return send_file('/app/static/index.html')

@app.route('/grant/<path:slug>')
@login_required
def grant_detail_page(slug): return send_file('/app/static/grant.html')

@app.route('/api/grant/<path:slug>')
@login_required
def api_grant_detail(slug):
    conn = get_db()
    row = conn.execute("SELECT * FROM grants WHERE slug=?", (slug,)).fetchone()
    conn.close()
    if not row: return jsonify({'error':'Not found'}), 404
    return jsonify(dict(row))

@app.route('/api/grants')
@login_required
def api_grants():
    conn     = get_db()
    page     = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 18))
    search   = request.args.get('search', '').strip()
    sort     = request.args.get('sort', 'deadline_asc')
    donor    = request.args.get('donor', '')
    size     = request.args.get('size', '')
    category = request.args.get('category', '')
    region   = request.args.get('region', '')
    eligible = request.args.get('eligible', '')
    # Default: show active only. Pass status=expired to see expired, status=all to see everything.
    status   = request.args.get('status', 'active')

    query  = "SELECT * FROM grants WHERE 1=1"
    params = []
    if search:
        query += " AND (title LIKE ? OR donor LIKE ? OR description LIKE ?)"
        params += ['%'+search+'%','%'+search+'%','%'+search+'%']
    if donor:    query += " AND donor=?";                 params.append(donor)
    if size:     query += " AND grant_size=?";            params.append(size)
    if category: query += " AND category=?";              params.append(category)
    if region:   query += " AND region=?";                params.append(region)
    if eligible: query += " AND eligible_org LIKE ?";     params.append('%'+eligible+'%')
    country  = request.args.get('country', '')
    if country:  query += " AND countries LIKE ?";        params.append('%'+country+'%')
    if status and status != 'all':
        query += " AND (status=? OR status IS NULL)";     params.append(status)

    sort_map = {
        'deadline_asc':  'COALESCE(deadline_iso, deadline) ASC',
        'deadline_desc': 'COALESCE(deadline_iso, deadline) DESC',
        'posted_desc':   'created_at DESC',
        'posted_asc':    'created_at ASC',
    }
    query += " ORDER BY " + sort_map.get(sort, 'COALESCE(deadline_iso, deadline) ASC')
    total  = conn.execute("SELECT COUNT(*) FROM (" + query + ")", params).fetchone()[0]
    query += " LIMIT " + str(per_page) + " OFFSET " + str((page-1)*per_page)
    grants = [dict(row) for row in conn.execute(query, params).fetchall()]
    conn.close()
    return jsonify({'grants':grants,'total':total,'page':page,'pages':(total+per_page-1)//per_page,'updated':datetime.utcnow().isoformat()})

@app.route('/api/stats')
@login_required
def api_stats():
    conn    = get_db()
    total   = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
    active  = conn.execute("SELECT COUNT(*) FROM grants WHERE status='active' OR status IS NULL").fetchone()[0]
    expired = conn.execute("SELECT COUNT(*) FROM grants WHERE status='expired'").fetchone()[0]
    donors  = conn.execute("SELECT COUNT(DISTINCT donor) FROM grants").fetchone()[0]
    conn.close()
    return jsonify({'total':total,'active':active,'expired':expired,'donors':donors})

@app.route('/api/filter-options')
@login_required
def filter_options():
    conn       = get_db()
    categories = [r[0] for r in conn.execute("SELECT DISTINCT category FROM grants WHERE category IS NOT NULL ORDER BY category").fetchall()]
    regions    = sorted(set(r[0].title() for r in conn.execute("SELECT DISTINCT region FROM grants WHERE region IS NOT NULL").fetchall() if r[0]))
    sizes      = [r[0] for r in conn.execute("SELECT DISTINCT grant_size FROM grants WHERE grant_size IS NOT NULL ORDER BY grant_size").fetchall()]
    donors     = [r[0] for r in conn.execute("SELECT DISTINCT donor FROM grants WHERE donor IS NOT NULL ORDER BY donor").fetchall()]
    elig_rows  = [r[0] for r in conn.execute("SELECT DISTINCT eligible_org FROM grants WHERE eligible_org IS NOT NULL AND eligible_org != ''").fetchall()]
    elig_set   = set()
    for row in elig_rows:
        for part in row.split(','):
            p = part.strip()
            if p: elig_set.add(p)
    # Countries — split comma-separated values, collect unique
    country_rows = [r[0] for r in conn.execute("SELECT DISTINCT countries FROM grants WHERE countries IS NOT NULL AND countries != '' AND countries != 'Global' ORDER BY countries").fetchall()]
    country_set  = set()
    for row in country_rows:
        for part in row.split(','):
            p = part.strip()
            if p and p != 'Global': country_set.add(p)
    conn.close()
    return jsonify({'categories':categories,'regions':regions,'sizes':sizes,'donors':donors,'eligible':sorted(elig_set),'countries':sorted(country_set)})

@app.route('/api/ingest', methods=['POST'])
def ingest():
    if request.headers.get('X-Secret','') != os.environ.get('INGEST_SECRET','uwezogrants2026'):
        return jsonify({'error':'Unauthorized'}), 401
    grants = request.json.get('grants', [])
    conn   = get_db()
    added  = 0
    today_iso = datetime.utcnow().strftime("%Y-%m-%d")
    for g in grants:
        gid  = hashlib.md5((g.get('title','')+g.get('deadline','')).encode()).hexdigest()
        slug = g.get('url','').split('/op/')[-1] if '/op/' in g.get('url','') else ''
        try:
            # The detail page's deadline is the real one ("Ongoing" in the list is
            # often a dated call). grant_id stays on the list deadline, so the
            # scraper's known-grant check keeps matching.
            shown_deadline = g.get('detailDeadline') or g.get('deadline','')
            deadline_iso = ''
            try:
                deadline_iso = datetime.strptime(shown_deadline, "%B %d, %Y").strftime("%Y-%m-%d")
            except Exception:
                pass
            # Skip inserting new grants that are already expired
            if deadline_iso and deadline_iso < today_iso:
                continue
            text      = g.get('text','') or ''
            ext_links = [u for u in re.findall(r'href=["\'](https?://[^"\'>]+)["\']', text)
                         if 'fundsforngos' not in u and 'fundsforngo' not in u]
            apply_url = g.get('applyLink','') or (ext_links[0] if ext_links else '')
            combined  = text + ' ' + (g.get('description','') or '')
            region    = detect_region(combined)
            eligible  = detect_eligible_org(combined)
            # Extract country mentions
            import re as _re2
            _COUNTRIES = ['Afghanistan','Albania','Algeria','Angola','Argentina','Armenia','Australia','Austria','Azerbaijan','Bangladesh','Belarus','Belgium','Benin','Bolivia','Bosnia','Botswana','Brazil','Bulgaria','Burkina Faso','Burundi','Cambodia','Cameroon','Canada','Chad','Chile','China','Colombia','Congo','Costa Rica','Croatia','Cuba','Denmark','Dominican Republic','DR Congo','Ecuador','Egypt','El Salvador','Ethiopia','Finland','France','Gambia','Georgia','Germany','Ghana','Greece','Guatemala','Guinea','Haiti','Honduras','Hungary','India','Indonesia','Iran','Iraq','Ireland','Israel','Italy','Jamaica','Japan','Jordan','Kazakhstan','Kenya','Kosovo','Kyrgyzstan','Laos','Lebanon','Lesotho','Liberia','Libya','Madagascar','Malawi','Malaysia','Mali','Mauritania','Mexico','Moldova','Mongolia','Montenegro','Morocco','Mozambique','Myanmar','Namibia','Nepal','Netherlands','Nicaragua','Niger','Nigeria','North Macedonia','Norway','Pakistan','Palestine','Panama','Papua New Guinea','Paraguay','Peru','Philippines','Poland','Portugal','Romania','Russia','Rwanda','Senegal','Serbia','Sierra Leone','Somalia','South Africa','South Sudan','Spain','Sri Lanka','Sudan','Sweden','Switzerland','Syria','Tajikistan','Tanzania','Thailand','Timor-Leste','Togo','Tunisia','Turkey','Turkmenistan','Uganda','Ukraine','United Kingdom','United States','Uruguay','Uzbekistan','Venezuela','Vietnam','Yemen','Zambia','Zimbabwe']
            _cl = combined.lower()
            countries = ', '.join([c for c in _COUNTRIES if _re2.search(r'\b'+_re2.escape(c.lower())+r'\b', _cl)]) or 'Global'
            cur = conn.execute(
                """INSERT OR IGNORE INTO grants
                   (grant_id,title,donor,grant_size,category,posted_date,deadline,deadline_iso,
                    url,slug,image,description,full_text,apply_url,region,eligible_org,status,countries)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (gid, g.get('title'), g.get('donorAgency'), g.get('grantSize'),
                 g.get('category'), g.get('posted'), shown_deadline, deadline_iso,
                 'https://grants.fundsforngospremium.com/'+g.get('url',''),
                 slug, g.get('image',''), g.get('description',''), text,
                 apply_url, region, eligible, 'active', countries))
            added += cur.rowcount   # 1 only when a genuinely new row was inserted
        except Exception:
            pass
    # Also mark any existing grants that just expired
    conn.execute(
        "UPDATE grants SET status='expired' WHERE deadline_iso IS NOT NULL AND deadline_iso != '' AND deadline_iso < ? AND status != 'expired'",
        (today_iso,)
    )
    conn.commit()
    conn.close()
    return jsonify({'added':added,'total':len(grants)})

# ── Public read-only API for the Fund Nest mobile app (no login) ─────────────
# LICENSING: grants are mirrored from a paid FundsforNGOs Premium account, so this API
# returns ONLY the factual fields below. Never add description, full_text, url or image.
PUBLIC_FIELDS = ('slug', 'title', 'donor', 'grant_size', 'category', 'region', 'eligible_org',
                 'countries', 'deadline', 'deadline_iso', 'posted_date', 'apply_url', 'status')
PUBLIC_PREFIX = '/api/public/'
PUBLIC_RATE_LIMIT = 120      # requests per IP per minute (in memory, per gunicorn worker)
PUBLIC_RATE_WINDOW = 60
PUBLIC_MAX_PER_PAGE = 50
PUBLIC_SORTS = {
    # grants with no date ("Ongoing") always sort last when sorting by deadline
    'deadline_asc':  "CASE WHEN deadline_iso IS NULL OR deadline_iso='' THEN 1 ELSE 0 END, deadline_iso ASC, id ASC",
    'deadline_desc': "CASE WHEN deadline_iso IS NULL OR deadline_iso='' THEN 1 ELSE 0 END, deadline_iso DESC, id DESC",
    'posted_desc':   "created_at DESC, id DESC",
    'posted_asc':    "created_at ASC, id ASC",
}
_rate_hits = {}   # ip -> list of request timestamps within the window

class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status

def _client_ip():
    # Behind Cloudflare + Coolify's proxy: prefer the real client IP they pass along.
    ip = request.headers.get('CF-Connecting-IP') or (request.headers.get('X-Forwarded-For', '').split(',')[0].strip())
    return ip or request.remote_addr or 'unknown'

def _rate_limited(ip):
    import time
    now = time.time()
    hits = [t for t in _rate_hits.get(ip, []) if now - t < PUBLIC_RATE_WINDOW]
    if len(hits) >= PUBLIC_RATE_LIMIT:
        _rate_hits[ip] = hits
        return int(PUBLIC_RATE_WINDOW - (now - hits[0])) + 1
    hits.append(now)
    _rate_hits[ip] = hits
    if len(_rate_hits) > 5000:   # keep memory bounded: drop idle clients
        for k in [k for k, v in _rate_hits.items() if not v or now - v[-1] >= PUBLIC_RATE_WINDOW]:
            _rate_hits.pop(k, None)
    return 0

@app.before_request
def _public_api_gate():
    if not request.path.startswith(PUBLIC_PREFIX) or request.method == 'OPTIONS':
        return None
    wait = _rate_limited(_client_ip())
    if wait:
        resp = jsonify({'error': 'Too many requests. Please slow down.'})
        resp.status_code = 429
        resp.headers['Retry-After'] = str(wait)
        return resp
    return None

@app.after_request
def _public_api_headers(resp):
    if request.path.startswith(PUBLIC_PREFIX):
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        if request.method == 'GET' and resp.status_code == 200:
            resp.headers['Cache-Control'] = 'public, max-age=300'
        else:
            resp.headers['Cache-Control'] = 'no-store'
    return resp

@app.errorhandler(ApiError)
def _api_error(e):
    return jsonify({'error': e.message}), e.status

@app.errorhandler(404)
def _not_found(e):
    if request.path.startswith(PUBLIC_PREFIX):
        return jsonify({'error': 'Not found'}), 404
    return e

@app.errorhandler(405)
def _bad_method(e):
    if request.path.startswith(PUBLIC_PREFIX):
        return jsonify({'error': 'Method not allowed'}), 405
    return e

@app.errorhandler(500)
def _server_error(e):
    if request.path.startswith(PUBLIC_PREFIX):
        return jsonify({'error': 'Something went wrong. Please try again later.'}), 500
    return e

def _public_apply_url(u):
    """Only the funder's own page. Drop anything that is not http(s) or points back at FundsforNGOs."""
    u = (u or '').strip()
    if not re.match(r'^https?://', u, re.I) or re.search(r'fundsforngo', u, re.I):
        return None
    return u

def _public_grant(row, today_iso):
    out = {k: row[k] for k in PUBLIC_FIELDS}
    out['apply_url'] = _public_apply_url(out['apply_url'])
    iso = out['deadline_iso'] or ''
    out['status'] = 'expired' if (out['status'] == 'expired' or (iso and iso < today_iso)) else 'active'
    return out

def _int_arg(name, default, lo, hi):
    raw = request.args.get(name)
    if raw is None or raw == '':
        return default
    try:
        val = int(raw)
    except ValueError:
        raise ApiError(name + ' must be a whole number')
    return max(lo, min(hi, val))

def _like(term):
    return '%' + term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'

@app.route('/api/public/v1/grants')
def public_grants():
    today_iso = datetime.utcnow().strftime('%Y-%m-%d')
    page     = _int_arg('page', 1, 1, 100000)
    per_page = _int_arg('per_page', 18, 1, PUBLIC_MAX_PER_PAGE)
    search   = request.args.get('search', '').strip()[:100]
    sort     = request.args.get('sort', 'deadline_asc')
    status   = request.args.get('status', 'active')
    if sort not in PUBLIC_SORTS:
        raise ApiError('sort must be one of: ' + ', '.join(PUBLIC_SORTS))
    if status not in ('active', 'expired', 'all'):
        raise ApiError('status must be active, expired or all')

    where, params = ["slug IS NOT NULL AND slug != ''"], []
    if search:
        # Title, funder, category and countries only. Never the mirrored description text.
        where.append("(title LIKE ? ESCAPE '\\' OR donor LIKE ? ESCAPE '\\' OR category LIKE ? ESCAPE '\\' OR countries LIKE ? ESCAPE '\\')")
        params += [_like(search)] * 4
    for col, arg in (('donor', 'donor'), ('grant_size', 'size'), ('category', 'category')):
        val = request.args.get(arg, '').strip()
        if val:
            where.append(col + " = ?"); params.append(val)
    region = request.args.get('region', '').strip()
    if region:
        where.append("region = ? COLLATE NOCASE"); params.append(region)
    eligible = request.args.get('eligible', '').strip()
    if eligible:
        where.append("eligible_org LIKE ? ESCAPE '\\'"); params.append(_like(eligible))
    country = request.args.get('country', '').strip()
    if country:
        # whole-name match inside the comma list, so "Niger" does not match "Nigeria"
        where.append("(',' || REPLACE(countries, ', ', ',') || ',') LIKE ? ESCAPE '\\'")
        params.append('%,' + _like(country)[1:-1] + ',%')
    if status == 'active':
        where.append("(status = 'active' OR status IS NULL OR status = '') AND (deadline_iso IS NULL OR deadline_iso = '' OR deadline_iso >= ?)")
        params.append(today_iso)
    elif status == 'expired':
        where.append("(status = 'expired' OR (deadline_iso IS NOT NULL AND deadline_iso != '' AND deadline_iso < ?))")
        params.append(today_iso)

    sql_where = ' WHERE ' + ' AND '.join(where)
    conn = get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM grants" + sql_where, params).fetchone()[0]
        rows = conn.execute(
            "SELECT " + ', '.join(PUBLIC_FIELDS) + " FROM grants" + sql_where +
            " ORDER BY " + PUBLIC_SORTS[sort] + " LIMIT ? OFFSET ?",
            params + [per_page, (page - 1) * per_page]).fetchall()
    finally:
        conn.close()
    return jsonify({'grants': [_public_grant(r, today_iso) for r in rows], 'total': total, 'page': page,
                    'per_page': per_page, 'pages': (total + per_page - 1) // per_page,
                    'updated': datetime.utcnow().isoformat()})

@app.route('/api/public/v1/grants/<path:slug>')
def public_grant(slug):
    today_iso = datetime.utcnow().strftime('%Y-%m-%d')
    conn = get_db()
    try:
        row = conn.execute("SELECT " + ', '.join(PUBLIC_FIELDS) + " FROM grants WHERE slug=?", (slug,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise ApiError('Grant not found', 404)
    return jsonify(_public_grant(row, today_iso))

@app.route('/api/public/v1/filters')
def public_filters():
    return filter_options.__wrapped__()

@app.route('/api/public/v1/stats')
def public_stats():
    today = datetime.utcnow().date()
    today_iso, in7_iso = today.isoformat(), (today + timedelta(days=7)).isoformat()
    week_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    live = "(status = 'active' OR status IS NULL OR status = '') AND (deadline_iso IS NULL OR deadline_iso = '' OR deadline_iso >= ?)"
    conn = get_db()
    try:
        active = conn.execute("SELECT COUNT(*) FROM grants WHERE " + live, (today_iso,)).fetchone()[0]
        closing = conn.execute("SELECT COUNT(*) FROM grants WHERE " + live + " AND deadline_iso != '' AND deadline_iso <= ?",
                               (today_iso, in7_iso)).fetchone()[0]
        added = conn.execute("SELECT COUNT(*) FROM grants WHERE " + live + " AND created_at >= ?",
                             (today_iso, week_ago)).fetchone()[0]
        last = conn.execute("SELECT finished_at FROM scrape_runs WHERE status='success' ORDER BY id DESC LIMIT 1").fetchone()
        if not (last and last[0]):
            last = conn.execute("SELECT MAX(created_at) FROM grants").fetchone()
    finally:
        conn.close()
    return jsonify({'active_total': active, 'closing_in_7_days': closing, 'added_this_week': added,
                    'last_updated': last[0] if last and last[0] else None})

# Public (no login) privacy policy for the Fund Nest app (linked from the Play listing and the app).
@app.route('/fundnest/privacy')
def fundnest_privacy():
    return send_file(os.path.join(STATIC_DIR, 'fundnest-privacy.html'), mimetype='text/html')

# ── Scraper trigger + status ─────────────────────────────────────────────────
SCRAPER_PATH = '/app/scraper.py'

def scrape_in_progress():
    """True if a scrape row is 'running' and its process is actually alive."""
    conn = get_db()
    row = conn.execute("SELECT pid, started_at FROM scrape_runs WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if not row: return False
    pid = row[0]
    if pid:
        try:
            os.kill(pid, 0)   # signal 0 = existence check
            return True
        except OSError:
            # stale 'running' row (process died) — mark it failed so we don't wedge
            try:
                c = get_db()
                c.execute("UPDATE scrape_runs SET status='failed', message='Process died unexpectedly', finished_at=CURRENT_TIMESTAMP WHERE status='running'")
                c.commit(); c.close()
            except Exception: pass
    return False

def launch_scraper(trigger='manual', mode='incremental'):
    env = dict(os.environ)
    env['SCRAPE_TRIGGER'] = trigger
    env['SCRAPE_MODE']    = mode
    # Detached so it outlives the request / worker that started it.
    subprocess.Popen([sys.executable, SCRAPER_PATH], env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)

@app.route('/api/run-scraper', methods=['POST'])
@login_required
def run_scraper():
    if scrape_in_progress():
        return jsonify({'ok': False, 'error': 'A scrape is already running.'}), 409
    mode = 'full' if (request.json or {}).get('mode') == 'full' else 'incremental'
    try:
        launch_scraper(trigger='manual', mode=mode)
        return jsonify({'ok': True, 'message': 'Scraper started.', 'mode': mode})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/scraper-status')
@login_required
def scraper_status():
    conn = get_db()
    row = conn.execute("SELECT * FROM scrape_runs ORDER BY id DESC LIMIT 1").fetchone()
    last_ok = conn.execute("SELECT finished_at FROM scrape_runs WHERE status='success' ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    running = scrape_in_progress()
    if not row:
        return jsonify({'running': False, 'status': 'never', 'message': 'Scraper has not run yet.'})
    r = dict(row)
    return jsonify({
        'running': running,
        'status': 'running' if running else r.get('status'),
        'message': r.get('message'),
        'trigger': r.get('trigger'),
        'fetched': r.get('fetched'),
        'added':   r.get('added'),
        'started_at':  r.get('started_at'),
        'finished_at': r.get('finished_at'),
        'last_success': last_ok[0] if last_ok else None,
    })

# ── Self-contained daily scheduler (no host cron needed) ─────────────────────
# Runs in exactly ONE gunicorn worker: whoever wins the flock owns the schedule.
def start_scheduler():
    try:
        lock = open('/data/.scheduler.lock', 'w')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        return  # another worker already owns the scheduler
    globals()['_sched_lock'] = lock  # keep fd alive for process lifetime

    from apscheduler.schedulers.background import BackgroundScheduler
    sched = BackgroundScheduler(timezone='UTC', daemon=True)
    # Daily automated run at 05:00 UTC (07:00 Kigali)
    sched.add_job(lambda: launch_scraper(trigger='scheduled', mode='incremental'),
                  'cron', hour=5, minute=0, id='daily_grants', misfire_grace_time=3600)
    sched.start()
    atexit.register(lambda: sched.shutdown(wait=False))

    # Catch-up: if the last successful run was >24h ago (e.g. server was down at 05:00), run now.
    try:
        conn = get_db()
        row = conn.execute("SELECT finished_at FROM scrape_runs WHERE status='success' ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        stale = True
        if row and row[0]:
            try:
                last = datetime.fromisoformat(str(row[0]).replace('Z',''))
                stale = (datetime.utcnow() - last) > timedelta(hours=24)
            except Exception:
                stale = True
        if stale and not scrape_in_progress():
            launch_scraper(trigger='scheduled', mode='incremental')
    except Exception:
        pass

init_db()
if os.environ.get('ENABLE_SCHEDULER', '1') == '1':
    start_scheduler()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
