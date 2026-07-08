import os, json, sqlite3, hashlib
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, render_template_string, request, session, redirect, url_for
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'g4r4nts-hub-secret-2026')
CORS(app)

SITE_PASSWORD = os.environ.get('SITE_PASSWORD', 'Kigali2020@')

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

DB_PATH = "/data/grants.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs("/data", exist_ok=True)
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grant_id TEXT UNIQUE,
            title TEXT,
            donor TEXT,
            grant_size TEXT,
            category TEXT,
            posted_date TEXT,
            deadline TEXT,
            url TEXT,
            image TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

LOGIN_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Grants Hub | Login</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'Segoe UI',sans-serif; background:linear-gradient(135deg,#1a56db 0%,#0d3b8e 100%); min-height:100vh; display:flex; align-items:center; justify-content:center; }
  .box { background:white; border-radius:16px; padding:48px 40px; width:100%; max-width:420px; box-shadow:0 20px 60px rgba(0,0,0,0.3); text-align:center; }
  .logo { font-size:3rem; margin-bottom:12px; }
  h1 { color:#1a202c; font-size:1.5rem; margin-bottom:6px; }
  p { color:#718096; font-size:0.9rem; margin-bottom:32px; }
  input { width:100%; padding:14px 16px; border:2px solid #e2e8f0; border-radius:10px; font-size:1rem; outline:none; margin-bottom:16px; transition:border 0.2s; }
  input:focus { border-color:#1a56db; }
  button { width:100%; padding:14px; background:#1a56db; color:white; border:none; border-radius:10px; font-size:1rem; font-weight:600; cursor:pointer; transition:background 0.2s; }
  button:hover { background:#1048c2; }
  .error { background:#fff5f5; color:#c53030; border:1px solid #feb2b2; border-radius:8px; padding:10px 14px; margin-bottom:16px; font-size:0.88rem; }
</style>
</head>
<body>
<div class="box">
  <div class="logo">🌍</div>
  <h1>Grants Hub</h1>
  <p>Uwezo Youth Empowerment<br>Enter the password to access</p>
  {% if error %}<div class="error">❌ Incorrect password. Try again.</div>{% endif %}
  <form method="POST" action="/login">
    <input type="password" name="password" placeholder="Enter password..." autofocus required>
    <button type="submit">Access Grants →</button>
  </form>
</div>
</body>
</html>"""

@app.route("/login", methods=["GET", "POST"])
def login_page():
    error = False
    if request.method == "POST":
        if request.form.get("password") == SITE_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('index'))
        error = True
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route("/")
@login_required
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/grants")
@login_required
def api_grants():
    conn = get_db()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    search = request.args.get("search", "").strip()
    sort = request.args.get("sort", "deadline_asc")
    donor = request.args.get("donor", "")
    size = request.args.get("size", "")

    query = "SELECT * FROM grants WHERE 1=1"
    params = []
    if search:
        query += " AND (title LIKE ? OR donor LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if donor:
        query += " AND donor = ?"
        params.append(donor)
    if size:
        query += " AND grant_size = ?"
        params.append(size)

    sort_map = {
        "deadline_asc": "deadline ASC",
        "deadline_desc": "deadline DESC",
        "posted_desc": "created_at DESC",
        "posted_asc": "created_at ASC",
        "size_asc": "grant_size ASC",
    }
    query += f" ORDER BY {sort_map.get(sort, 'deadline ASC')}"
    
    total = conn.execute(f"SELECT COUNT(*) FROM ({query})", params).fetchone()[0]
    query += f" LIMIT {per_page} OFFSET {(page-1)*per_page}"
    grants = [dict(row) for row in conn.execute(query, params).fetchall()]
    conn.close()

    return jsonify({
        "grants": grants,
        "total": total,
        "page": page,
        "pages": (total + per_page - 1) // per_page,
        "updated": datetime.utcnow().isoformat()
    })

@app.route("/api/stats")
@login_required
def api_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
    today = conn.execute("SELECT COUNT(*) FROM grants WHERE date(created_at) = date('now')").fetchone()[0]
    donors = conn.execute("SELECT COUNT(DISTINCT donor) FROM grants").fetchone()[0]
    conn.close()
    return jsonify({"total": total, "today": today, "donors": donors})

@app.route("/api/ingest", methods=["POST"])
def ingest():
    secret = request.headers.get("X-Secret", "")
    if secret != os.environ.get("INGEST_SECRET", "uwezogrants2026"):
        return jsonify({"error": "Unauthorized"}), 401
    
    grants = request.json.get("grants", [])
    conn = get_db()
    added = 0
    for g in grants:
        gid = hashlib.md5((g.get("title","") + g.get("deadline","")).encode()).hexdigest()
        try:
            conn.execute("""
                INSERT OR IGNORE INTO grants (grant_id, title, donor, grant_size, category, posted_date, deadline, url, image)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (gid, g.get("title"), g.get("donorAgency"), g.get("grantSize"),
                  g.get("category"), g.get("posted"), g.get("deadline"),
                  "https://grants.fundsforngospremium.com/" + g.get("url",""),
                  g.get("image","")))
            added += 1
        except: pass
    conn.commit()
    conn.close()
    return jsonify({"added": added, "total": len(grants)})

@app.route("/api/donors")
@login_required
def donors():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT donor FROM grants ORDER BY donor").fetchall()
    conn.close()
    return jsonify([r[0] for r in rows])

@app.route("/api/sizes")
@login_required
def sizes():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT grant_size FROM grants ORDER BY grant_size").fetchall()
    conn.close()
    return jsonify([r[0] for r in rows if r[0]])

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Grants Hub | Uwezo Youth Empowerment</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', sans-serif; background: #f0f4f8; color: #1a202c; }
  header { background: linear-gradient(135deg, #1a56db 0%, #0d3b8e 100%); color: white; padding: 24px 32px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 10px rgba(0,0,0,0.2); }
  header h1 { font-size: 1.8rem; font-weight: 700; }
  header p { font-size: 0.9rem; opacity: 0.8; margin-top: 4px; }
  .stats-bar { background: white; padding: 16px 32px; display: flex; gap: 32px; border-bottom: 1px solid #e2e8f0; }
  .stat { text-align: center; }
  .stat-number { font-size: 1.6rem; font-weight: 700; color: #1a56db; }
  .stat-label { font-size: 0.75rem; color: #718096; text-transform: uppercase; letter-spacing: 0.5px; }
  .controls { padding: 20px 32px; background: white; border-bottom: 1px solid #e2e8f0; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
  .search-box { flex: 1; min-width: 240px; padding: 10px 16px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 0.95rem; outline: none; }
  .search-box:focus { border-color: #1a56db; box-shadow: 0 0 0 3px rgba(26,86,219,0.1); }
  select { padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 0.9rem; background: white; cursor: pointer; outline: none; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
  .badge-grant { background: #dbeafe; color: #1e40af; }
  .badge-event { background: #fef3c7; color: #92400e; }
  .badge-fellowship { background: #d1fae5; color: #065f46; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 20px; padding: 24px 32px; }
  .card { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.08); transition: transform 0.2s, box-shadow 0.2s; }
  .card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.12); }
  .card-img { width: 100%; height: 160px; object-fit: cover; background: #e2e8f0; }
  .card-body { padding: 16px; }
  .card-title { font-size: 0.95rem; font-weight: 600; line-height: 1.4; margin-bottom: 10px; color: #1a202c; }
  .card-meta { display: flex; flex-direction: column; gap: 6px; font-size: 0.82rem; color: #4a5568; }
  .card-meta span { display: flex; align-items: center; gap: 6px; }
  .deadline { color: #c53030; font-weight: 600; }
  .deadline.soon { background: #fff5f5; padding: 4px 8px; border-radius: 6px; border: 1px solid #feb2b2; }
  .card-footer { padding: 12px 16px; border-top: 1px solid #f0f4f8; }
  .btn { display: inline-block; padding: 8px 18px; background: #1a56db; color: white; border-radius: 7px; text-decoration: none; font-size: 0.85rem; font-weight: 600; transition: background 0.2s; }
  .btn:hover { background: #1048c2; }
  .pagination { display: flex; justify-content: center; gap: 8px; padding: 24px; }
  .page-btn { padding: 8px 14px; border: 1px solid #e2e8f0; border-radius: 7px; cursor: pointer; background: white; font-size: 0.9rem; }
  .page-btn.active { background: #1a56db; color: white; border-color: #1a56db; }
  .page-btn:hover:not(.active) { background: #f0f4f8; }
  .loading { text-align: center; padding: 60px; color: #718096; font-size: 1.1rem; }
  .updated { text-align: center; padding: 8px; font-size: 0.78rem; color: #a0aec0; }
  @media (max-width: 600px) { .grid { padding: 12px; grid-template-columns: 1fr; } .controls { padding: 12px; } header { padding: 16px; } }
</style>
</head>
<body>
<header>
  <div>
    <h1>🌍 Grants Hub</h1>
    <p>Uwezo Youth Empowerment | Updated daily from fundsforNGOs Premium</p>
  </div>
  <div style="text-align:right; font-size:0.85rem; opacity:0.9; display:flex; align-items:center; gap:16px;">
    <div id="last-updated">Loading...</div>
    <a href="/logout" style="color:white;opacity:0.7;text-decoration:none;font-size:0.8rem;border:1px solid rgba(255,255,255,0.4);padding:5px 12px;border-radius:6px;">Logout</a>
  </div>
</header>

<div class="stats-bar">
  <div class="stat"><div class="stat-number" id="stat-total">—</div><div class="stat-label">Total Grants</div></div>
  <div class="stat"><div class="stat-number" id="stat-today">—</div><div class="stat-label">Added Today</div></div>
  <div class="stat"><div class="stat-number" id="stat-donors">—</div><div class="stat-label">Donors</div></div>
</div>

<div class="controls">
  <input class="search-box" id="search" placeholder="🔍  Search grants, donors..." oninput="debounceSearch()">
  <select id="sort" onchange="loadGrants()">
    <option value="deadline_asc">Deadline: Soonest</option>
    <option value="deadline_desc">Deadline: Latest</option>
    <option value="posted_desc">Newest Posted</option>
    <option value="size_asc">Grant Size</option>
  </select>
  <select id="donor-filter" onchange="loadGrants()">
    <option value="">All Donors</option>
  </select>
  <select id="size-filter" onchange="loadGrants()">
    <option value="">All Sizes</option>
  </select>
</div>

<div id="grants-grid" class="grid"><div class="loading">Loading grants...</div></div>
<div class="pagination" id="pagination"></div>
<div class="updated" id="updated-text"></div>

<script>
let currentPage = 1;
let searchTimer;

async function loadStats() {
  const r = await fetch('/api/stats');
  const d = await r.json();
  document.getElementById('stat-total').textContent = d.total.toLocaleString();
  document.getElementById('stat-today').textContent = d.today;
  document.getElementById('stat-donors').textContent = d.donors;
}

async function loadFilters() {
  const [donors, sizes] = await Promise.all([fetch('/api/donors').then(r=>r.json()), fetch('/api/sizes').then(r=>r.json())]);
  const dd = document.getElementById('donor-filter');
  donors.forEach(d => { const o=document.createElement('option'); o.value=d; o.textContent=d; dd.appendChild(o); });
  const sd = document.getElementById('size-filter');
  sizes.forEach(s => { const o=document.createElement('option'); o.value=s; o.textContent=s; sd.appendChild(o); });
}

function daysUntil(dateStr) {
  const d = new Date(dateStr);
  const today = new Date();
  return Math.ceil((d - today) / (1000*60*60*24));
}

async function loadGrants() {
  const search = document.getElementById('search').value;
  const sort = document.getElementById('sort').value;
  const donor = document.getElementById('donor-filter').value;
  const size = document.getElementById('size-filter').value;
  
  const params = new URLSearchParams({ page: currentPage, per_page: 18, search, sort, donor, size });
  const r = await fetch('/api/grants?' + params);
  const data = await r.json();
  
  const grid = document.getElementById('grants-grid');
  if (!data.grants.length) { grid.innerHTML = '<div class="loading">No grants found matching your filters.</div>'; return; }
  
  grid.innerHTML = data.grants.map(g => {
    const days = daysUntil(g.deadline);
    const deadlineClass = days <= 7 ? 'deadline soon' : 'deadline';
    const deadlineText = days < 0 ? 'Expired' : days === 0 ? 'Today!' : days === 1 ? 'Tomorrow!' : `${days} days left`;
    const badge = g.category === 'Grant' ? 'badge-grant' : g.category === 'Events' ? 'badge-event' : 'badge-fellowship';
    return \`<div class="card">
      <img class="card-img" src="\${g.image}" onerror="this.style.background='#e2e8f0';this.src=''" alt="">
      <div class="card-body">
        <div style="margin-bottom:8px"><span class="badge \${badge}">\${g.category||'Grant'}</span></div>
        <div class="card-title">\${g.title}</div>
        <div class="card-meta">
          <span>🏢 \${g.donor}</span>
          <span>💰 \${g.grant_size||'Not specified'}</span>
          <span>📅 Posted: \${g.posted_date}</span>
          <span class="\${deadlineClass}">⏰ \${g.deadline} — \${deadlineText}</span>
        </div>
      </div>
      <div class="card-footer"><a href="\${g.url}" target="_blank" class="btn">View & Apply →</a></div>
    </div>\`;
  }).join('');
  
  renderPagination(data.page, data.pages);
  document.getElementById('updated-text').textContent = 'Last synced: ' + new Date(data.updated).toLocaleString();
  document.getElementById('last-updated').textContent = data.total + ' grants available';
}

function renderPagination(current, total) {
  if (total <= 1) { document.getElementById('pagination').innerHTML = ''; return; }
  let html = '';
  if (current > 1) html += \`<button class="page-btn" onclick="goPage(\${current-1})">‹</button>\`;
  for (let i = Math.max(1, current-2); i <= Math.min(total, current+2); i++) {
    html += \`<button class="page-btn \${i===current?'active':''}" onclick="goPage(\${i})">\${i}</button>\`;
  }
  if (current < total) html += \`<button class="page-btn" onclick="goPage(\${current+1})">›</button>\`;
  document.getElementById('pagination').innerHTML = html;
}

function goPage(p) { currentPage = p; loadGrants(); window.scrollTo(0,200); }
function debounceSearch() { clearTimeout(searchTimer); searchTimer = setTimeout(() => { currentPage=1; loadGrants(); }, 400); }

loadStats(); loadFilters(); loadGrants();
</script>
</body>
</html>"""

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
