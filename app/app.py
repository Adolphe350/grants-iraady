import os, sqlite3, hashlib
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    for col in ['deadline_iso','slug','description','full_text','apply_url']:
        try:
            conn.execute("ALTER TABLE grants ADD COLUMN " + col + " TEXT")
        except Exception:
            pass
    conn.commit()
    rows = conn.execute("SELECT id, deadline, url FROM grants WHERE deadline_iso IS NULL OR deadline_iso=''").fetchall()
    for row in rows:
        try:
            dt = datetime.strptime(row[1], "%B %d, %Y")
            slug = row[2].split('/op/')[-1] if '/op/' in (row[2] or '') else ''
            conn.execute("UPDATE grants SET deadline_iso=?, slug=? WHERE id=?",
                         (dt.strftime("%Y-%m-%d"), slug, row[0]))
        except Exception:
            pass
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    error = False
    if request.method == 'POST':
        if request.form.get('password') == SITE_PASSWORD:
            session.permanent = True
            session['authenticated'] = True
            return redirect(url_for('index'))
        error = True
    html = open('/app/static/login.html').read()
    if error:
        html = html.replace('<!--ERROR-->', '<div class="error">Incorrect password. Try again.</div>')
    return html, 200, {'Content-Type': 'text/html'}

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/')
@login_required
def index():
    return send_file('/app/static/index.html')

@app.route('/grant/<path:slug>')
@login_required
def grant_detail_page(slug):
    return send_file('/app/static/grant.html')

@app.route('/api/grant/<path:slug>')
@login_required
def api_grant_detail(slug):
    conn = get_db()
    row = conn.execute("SELECT * FROM grants WHERE slug=?", (slug,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Not found'}), 404
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
    query  = "SELECT * FROM grants WHERE 1=1"
    params = []
    if search:
        query += " AND (title LIKE ? OR donor LIKE ?)"
        params += ['%'+search+'%', '%'+search+'%']
    if donor:
        query += " AND donor=?"; params.append(donor)
    if size:
        query += " AND grant_size=?"; params.append(size)
    sort_map = {
        'deadline_asc':  'COALESCE(deadline_iso, deadline) ASC',
        'deadline_desc': 'COALESCE(deadline_iso, deadline) DESC',
        'posted_desc':   'created_at DESC',
        'posted_asc':    'created_at ASC',
    }
    query += " ORDER BY " + sort_map.get(sort, 'COALESCE(deadline_iso, deadline) ASC')
    total = conn.execute("SELECT COUNT(*) FROM ("+query+")", params).fetchone()[0]
    query += " LIMIT "+str(per_page)+" OFFSET "+str((page-1)*per_page)
    grants = [dict(row) for row in conn.execute(query, params).fetchall()]
    conn.close()
    return jsonify({'grants': grants, 'total': total, 'page': page,
                    'pages': (total+per_page-1)//per_page,
                    'updated': datetime.utcnow().isoformat()})

@app.route('/api/stats')
@login_required
def api_stats():
    conn = get_db()
    total  = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
    today  = conn.execute("SELECT COUNT(*) FROM grants WHERE date(created_at)=date('now')").fetchone()[0]
    donors = conn.execute("SELECT COUNT(DISTINCT donor) FROM grants").fetchone()[0]
    conn.close()
    return jsonify({'total': total, 'today': today, 'donors': donors})

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
            try:
                deadline_iso = datetime.strptime(g.get('deadline',''), "%B %d, %Y").strftime("%Y-%m-%d")
            except Exception:
                pass
            conn.execute(
                """INSERT OR IGNORE INTO grants
                   (grant_id,title,donor,grant_size,category,posted_date,deadline,deadline_iso,url,slug,image,description,full_text,apply_url)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (gid, g.get('title'), g.get('donorAgency'), g.get('grantSize'),
                 g.get('category'), g.get('posted'), g.get('deadline'), deadline_iso,
                 'https://grants.fundsforngospremium.com/'+g.get('url',''),
                 slug, g.get('image',''),
                 g.get('description',''), g.get('text',''), g.get('applyLink','')))
            added += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return jsonify({'added': added, 'total': len(grants)})

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
