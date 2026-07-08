import os, sqlite3, hashlib, re
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
DB_PATH = '/data/grants.db'

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
        'africa':['rwanda','kenya','nigeria','ghana','ethiopia','tanzania','uganda','zambia','malawi','mozambique','cameroon','senegal','mali','niger','chad','sudan','angola','zimbabwe','botswana','namibia','lesotho','swaziland','eswatini','south africa','egypt','morocco','tunisia','algeria','libya'],
        'Asia':['india','china','bangladesh','pakistan','nepal','sri lanka','myanmar','vietnam','thailand','indonesia','philippines','cambodia','laos','malaysia'],
        'Americas':['united states','usa','canada','brazil','mexico','colombia','peru','chile','argentina','venezuela'],
        'Europe':['europe','european','uk','united kingdom','france','germany','spain','italy','netherlands','sweden'],
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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs('/data', exist_ok=True)
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS grants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grant_id TEXT UNIQUE, title TEXT, donor TEXT,
        grant_size TEXT, category TEXT, posted_date TEXT,
        deadline TEXT, deadline_iso TEXT, url TEXT, image TEXT,
        slug TEXT, description TEXT, full_text TEXT, apply_url TEXT,
        region TEXT, eligible_org TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    for col in ['deadline_iso','slug','description','full_text','apply_url','region','eligible_org']:
        try: conn.execute("ALTER TABLE grants ADD COLUMN " + col + " TEXT")
        except: pass
    conn.commit()
    # Backfill region/eligible_org for existing rows
    rows = conn.execute("SELECT id, deadline, url, full_text, description FROM grants WHERE region IS NULL OR region=''").fetchall()
    for row in rows:
        text = (row[3] or '') + ' ' + (row[4] or '')
        slug = row[2].split('/op/')[-1] if '/op/' in (row[2] or '') else ''
        deadline_iso = ''
        try:
            deadline_iso = datetime.strptime(row[1], "%B %d, %Y").strftime("%Y-%m-%d")
        except: pass
        region = detect_region(text)
        eligible = detect_eligible_org(text)
        conn.execute("UPDATE grants SET region=?, eligible_org=?, deadline_iso=COALESCE(NULLIF(deadline_iso,''),?), slug=COALESCE(NULLIF(slug,''),?) WHERE id=?",
                     (region, eligible, deadline_iso, slug, row[0]))
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
    conn = get_db()
    page     = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 18))
    search   = request.args.get('search', '').strip()
    sort     = request.args.get('sort', 'deadline_asc')
    donor    = request.args.get('donor', '')
    size     = request.args.get('size', '')
    category = request.args.get('category', '')
    region   = request.args.get('region', '')
    eligible = request.args.get('eligible', '')
    query  = "SELECT * FROM grants WHERE 1=1"
    params = []
    if search:
        query += " AND (title LIKE ? OR donor LIKE ? OR description LIKE ?)"
        params += ['%'+search+'%','%'+search+'%','%'+search+'%']
    if donor:    query += " AND donor=?";          params.append(donor)
    if size:     query += " AND grant_size=?";     params.append(size)
    if category: query += " AND category=?";       params.append(category)
    if region:   query += " AND region=?";         params.append(region)
    if eligible: query += " AND eligible_org LIKE ?"; params.append('%'+eligible+'%')
    sort_map = {
        'deadline_asc':  'COALESCE(deadline_iso, deadline) ASC',
        'deadline_desc': 'COALESCE(deadline_iso, deadline) DESC',
        'posted_desc':   'created_at DESC',
        'posted_asc':    'created_at ASC',
    }
    query += " ORDER BY " + sort_map.get(sort, 'COALESCE(deadline_iso, deadline) ASC')
    total = conn.execute("SELECT COUNT(*) FROM (" + query + ")", params).fetchone()[0]
    query += " LIMIT " + str(per_page) + " OFFSET " + str((page-1)*per_page)
    grants = [dict(row) for row in conn.execute(query, params).fetchall()]
    conn.close()
    return jsonify({'grants':grants,'total':total,'page':page,'pages':(total+per_page-1)//per_page,'updated':datetime.utcnow().isoformat()})

@app.route('/api/stats')
@login_required
def api_stats():
    conn = get_db()
    total  = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
    today  = conn.execute("SELECT COUNT(*) FROM grants WHERE date(created_at)=date('now')").fetchone()[0]
    donors = conn.execute("SELECT COUNT(DISTINCT donor) FROM grants").fetchone()[0]
    conn.close()
    return jsonify({'total':total,'today':today,'donors':donors})

@app.route('/api/filter-options')
@login_required
def filter_options():
    conn = get_db()
    categories = [r[0] for r in conn.execute("SELECT DISTINCT category FROM grants WHERE category IS NOT NULL ORDER BY category").fetchall()]
    regions    = sorted(set(r[0].title() for r in conn.execute("SELECT DISTINCT region FROM grants WHERE region IS NOT NULL").fetchall() if r[0]))
    sizes      = [r[0] for r in conn.execute("SELECT DISTINCT grant_size FROM grants WHERE grant_size IS NOT NULL ORDER BY grant_size").fetchall()]
    donors     = [r[0] for r in conn.execute("SELECT DISTINCT donor FROM grants WHERE donor IS NOT NULL ORDER BY donor").fetchall()]
    # eligible_org can be multi-value; collect unique tokens
    elig_rows  = [r[0] for r in conn.execute("SELECT DISTINCT eligible_org FROM grants WHERE eligible_org IS NOT NULL AND eligible_org != ''").fetchall()]
    elig_set   = set()
    for row in elig_rows:
        for part in row.split(','):
            p = part.strip()
            if p: elig_set.add(p)
    conn.close()
    return jsonify({'categories':categories,'regions':regions,'sizes':sizes,'donors':donors,'eligible':sorted(elig_set)})

@app.route('/api/ingest', methods=['POST'])
def ingest():
    if request.headers.get('X-Secret','') != os.environ.get('INGEST_SECRET','uwezogrants2026'):
        return jsonify({'error':'Unauthorized'}), 401
    grants = request.json.get('grants', [])
    conn   = get_db()
    added  = 0
    for g in grants:
        gid  = hashlib.md5((g.get('title','')+g.get('deadline','')).encode()).hexdigest()
        slug = g.get('url','').split('/op/')[-1] if '/op/' in g.get('url','') else ''
        try:
            deadline_iso = ''
            try: deadline_iso = datetime.strptime(g.get('deadline',''), "%B %d, %Y").strftime("%Y-%m-%d")
            except: pass
            text = g.get('text','') or ''
            ext_links = [u for u in re.findall(r'href=["\'](https?://[^"\'>]+)["\']', text) if 'fundsforngos' not in u and 'fundsforngo' not in u]
            apply_url  = g.get('applyLink','') or (ext_links[0] if ext_links else '')
            combined   = text + ' ' + (g.get('description','') or '')
            region     = detect_region(combined)
            eligible   = detect_eligible_org(combined)
            conn.execute("""INSERT OR IGNORE INTO grants
                (grant_id,title,donor,grant_size,category,posted_date,deadline,deadline_iso,url,slug,image,description,full_text,apply_url,region,eligible_org)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (gid, g.get('title'), g.get('donorAgency'), g.get('grantSize'),
                 g.get('category'), g.get('posted'), g.get('deadline'), deadline_iso,
                 'https://grants.fundsforngospremium.com/'+g.get('url',''),
                 slug, g.get('image',''), g.get('description',''), text, apply_url, region, eligible))
            added += 1
        except: pass
    conn.commit()
    conn.close()
    return jsonify({'added':added,'total':len(grants)})

@app.route('/api/donors')
@login_required
def donors():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT donor FROM grants ORDER BY donor").fetchall()
    conn.close()
    return jsonify([r[0] for r in rows if r[0]])

@app.route('/api/sizes')
@login_required
def sizes():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT grant_size FROM grants ORDER BY grant_size").fetchall()
    conn.close()
    return jsonify([r[0] for r in rows if r[0]])

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
