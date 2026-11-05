"""Tests for the public Fund Nest API. Run from the repo root:
    GRANTS_DB_PATH=<tmp>/grants.db ENABLE_SCHEDULER=0 python -m pytest tests -q
"""
import os, sys, tempfile, sqlite3, importlib
from datetime import datetime, timedelta

import pytest

TMP = tempfile.mkdtemp(prefix='grants-test-')
os.environ['GRANTS_DB_PATH'] = os.path.join(TMP, 'grants.db')
os.environ['ENABLE_SCHEDULER'] = '0'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
import app as appmod  # noqa: E402

CANARY = 'FFN-WRITTEN-TEXT-CANARY'
FFN_URL = 'https://grants.fundsforngospremium.com/op/secret-page'
today = datetime.utcnow().date()
iso = lambda d: (today + timedelta(days=d)).isoformat()


def seed():
    conn = appmod.get_db()
    rows = [
        # slug, title, donor, size, category, deadline_iso, region, eligible, countries, apply_url, status, age_days
        ('g-soon', 'Women Health Fund', 'Alpha Foundation', 'Up to $50,000', 'Health', iso(3), 'Africa', 'NGO', 'Kenya, Uganda', 'https://alpha.org/apply', 'active', 1),
        ('g-mid', 'Education Grant', 'Beta Trust', 'Up to $10,000', 'Education', iso(30), 'Asia', 'NGO, Academic', 'Nigeria', 'https://beta.org/apply', 'active', 20),
        ('g-niger', 'Niger Water Call', 'Gamma Org', 'Up to $10,000', 'Water', iso(10), 'West Africa', 'NGO', 'Niger', '', 'active', 2),
        ('g-ongoing', 'Rolling Climate Fund', 'Delta', 'Varies', 'Climate', '', 'Global', 'NGO', 'Global', 'https://delta.org', 'active', 3),
        ('g-old', 'Old Call', 'Alpha Foundation', 'Up to $5,000', 'Health', iso(-5), 'Africa', 'NGO', 'Kenya', 'https://alpha.org/old', 'expired', 90),
        ('g-ffn', 'Leaky Apply Link', 'Eps', 'Up to $1,000', 'Health', iso(5), 'Africa', 'NGO', 'Kenya', 'https://www.fundsforngos.org/x', 'active', 4),
    ]
    for i, r in enumerate(rows):
        created = (datetime.utcnow() - timedelta(days=r[11])).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            """INSERT INTO grants (grant_id,title,donor,grant_size,category,posted_date,deadline,deadline_iso,url,image,
               slug,description,full_text,apply_url,region,eligible_org,status,countries,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ('id%d' % i, r[1], r[2], r[3], r[4], 'Nov 1, 2026', r[5] or 'Ongoing', r[5], FFN_URL, 'https://img/x.png',
             r[0], CANARY + ' description', CANARY + ' full text', r[9], r[6], r[7], r[10], r[8], created))
    conn.commit(); conn.close()


@pytest.fixture(scope='module')
def client():
    seed()
    return appmod.app.test_client()


@pytest.fixture(autouse=True)
def reset_rate():
    appmod._rate_hits.clear()


def test_list_whitelist_and_no_leak(client):
    r = client.get('/api/public/v1/grants?status=all')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert CANARY not in body and 'fundsforngospremium' not in body and 'img/x.png' not in body
    for g in r.get_json()['grants']:
        assert set(g.keys()) == set(appmod.PUBLIC_FIELDS)


def test_default_status_active_and_sorted(client):
    j = client.get('/api/public/v1/grants').get_json()
    slugs = [g['slug'] for g in j['grants']]
    assert 'g-old' not in slugs
    assert slugs == ['g-soon', 'g-ffn', 'g-niger', 'g-mid', 'g-ongoing']   # ongoing last
    assert j['total'] == 5 and j['pages'] == 1


def test_expired_and_all(client):
    assert [g['slug'] for g in client.get('/api/public/v1/grants?status=expired').get_json()['grants']] == ['g-old']
    assert client.get('/api/public/v1/grants?status=all').get_json()['total'] == 6
    assert client.get('/api/public/v1/grants?status=bogus').status_code == 400


def test_filters(client):
    q = lambda s: [g['slug'] for g in client.get('/api/public/v1/grants?' + s).get_json()['grants']]
    assert q('search=women') == ['g-soon']
    assert q('search=alpha') == ['g-soon']
    assert q('donor=Beta Trust') == ['g-mid']
    assert q('category=Water') == ['g-niger']
    assert q('region=africa') == ['g-soon', 'g-ffn']          # exact region, case-insensitive
    assert q('eligible=Academic') == ['g-mid']
    assert q('size=Varies') == ['g-ongoing']
    assert q('country=Niger') == ['g-niger']                  # not Nigeria
    assert q('country=Nigeria') == ['g-mid']
    assert q('country=Uganda') == ['g-soon']


def test_search_does_not_match_description(client):
    assert client.get('/api/public/v1/grants?search=' + CANARY).get_json()['total'] == 0


def test_search_wildcards_escaped(client):
    assert client.get('/api/public/v1/grants?search=%25').get_json()['total'] == 0


def test_sort_and_paging(client):
    j = client.get('/api/public/v1/grants?sort=posted_desc&per_page=2&page=2').get_json()
    assert j['per_page'] == 2 and j['page'] == 2 and j['pages'] == 3
    assert [g['slug'] for g in j['grants']] == ['g-ongoing', 'g-ffn']
    assert client.get('/api/public/v1/grants?per_page=999').get_json()['per_page'] == 50
    assert client.get('/api/public/v1/grants?page=abc').status_code == 400
    assert client.get('/api/public/v1/grants?sort=nope').status_code == 400


def test_apply_url_never_ffn(client):
    g = client.get('/api/public/v1/grants/g-ffn').get_json()
    assert g['apply_url'] is None
    assert client.get('/api/public/v1/grants/g-niger').get_json()['apply_url'] is None   # empty -> null
    assert client.get('/api/public/v1/grants/g-soon').get_json()['apply_url'] == 'https://alpha.org/apply'


def test_single_grant_and_404(client):
    r = client.get('/api/public/v1/grants/g-old')
    assert r.status_code == 200 and r.get_json()['status'] == 'expired'
    assert CANARY not in r.get_data(as_text=True)
    r = client.get('/api/public/v1/grants/nope')
    assert r.status_code == 404 and r.get_json()['error']
    r = client.get('/api/public/v1/unknown')
    assert r.status_code == 404 and r.is_json


def test_filters_endpoint(client):
    j = client.get('/api/public/v1/filters').get_json()
    assert set(j) == {'categories', 'regions', 'sizes', 'donors', 'eligible', 'countries'}
    assert 'Kenya' in j['countries'] and 'Academic' in j['eligible']


def test_stats(client):
    j = client.get('/api/public/v1/stats').get_json()
    assert j['active_total'] == 5
    assert j['closing_in_7_days'] == 2          # g-soon (3d) and g-ffn (5d)
    assert j['added_this_week'] == 4            # soon, niger, ongoing, ffn
    assert j['last_updated']


def test_headers(client):
    r = client.get('/api/public/v1/stats')
    assert r.headers['Access-Control-Allow-Origin'] == '*'
    assert r.headers['Cache-Control'] == 'public, max-age=300'
    r = client.get('/api/public/v1/grants/nope')
    assert r.headers['Cache-Control'] == 'no-store'
    r = client.open('/api/public/v1/grants', method='OPTIONS', headers={'Origin': 'https://x.test', 'Access-Control-Request-Method': 'GET'})
    assert r.status_code in (200, 204) and r.headers['Access-Control-Allow-Origin'] == '*'


def test_post_rejected_json(client):
    r = client.post('/api/public/v1/grants')
    assert r.status_code == 405 and r.is_json


def test_rate_limit(client):
    for _ in range(appmod.PUBLIC_RATE_LIMIT):
        assert client.get('/api/public/v1/stats', headers={'CF-Connecting-IP': '9.9.9.9'}).status_code == 200
    r = client.get('/api/public/v1/stats', headers={'CF-Connecting-IP': '9.9.9.9'})
    assert r.status_code == 429 and r.is_json and int(r.headers['Retry-After']) > 0
    assert client.get('/api/public/v1/stats', headers={'CF-Connecting-IP': '8.8.8.8'}).status_code == 200


def test_existing_api_still_protected(client):
    assert client.get('/api/grants').status_code == 401
    assert client.get('/api/stats').status_code == 401


def test_privacy_page(client):
    r = client.get('/fundnest/privacy')
    assert r.status_code == 200 and r.mimetype == 'text/html'
    html = r.get_data(as_text=True)
    assert '16951380' in html and 'info@iraady.com' in html and 'Reset app data' in html
    assert '<script' not in html.lower()
