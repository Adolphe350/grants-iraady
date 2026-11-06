"""Tests for the additive read-only UI endpoints (/api/overview, closing_within / posted_within filters).
Run from the repo root:  GRANTS_DB_PATH=<tmp>/grants.db ENABLE_SCHEDULER=0 python -m pytest tests -q
"""
import os, sys, tempfile
from datetime import datetime, timedelta

import pytest

TMP = tempfile.mkdtemp(prefix='grants-ui-test-')
os.environ.setdefault('GRANTS_DB_PATH', os.path.join(TMP, 'grants.db'))
os.environ['ENABLE_SCHEDULER'] = '0'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
import app as appmod  # noqa: E402

today = datetime.utcnow().date()
iso = lambda d: (today + timedelta(days=d)).isoformat()
posted = lambda d: (today + timedelta(days=d)).strftime('%B %d, %Y')   # same format the scraper stores


def seed():
    conn = appmod.get_db()
    rows = [
        # slug, deadline offset (days), posted offset (days), status, region
        ('uitest-today', 0, -1, 'active', 'Africa'),
        ('uitest-3', 3, -2, 'active', 'Africa'),
        ('uitest-10', 10, -9, 'active', 'Asia'),
        ('uitest-60', 60, -30, 'active', 'Global'),
        ('uitest-old', -4, -40, 'expired', 'Global'),
    ]
    for i, (slug, dl, pd, status, region) in enumerate(rows):
        conn.execute(
            """INSERT INTO grants (grant_id,title,donor,grant_size,category,posted_date,deadline,deadline_iso,url,slug,
               description,full_text,apply_url,region,eligible_org,status,countries,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ('uitest%d' % i, 'UITEST ' + slug, 'UITEST Funder', 'Not Available', 'Grant', posted(pd), posted(dl), iso(dl),
             'https://x/' + slug, slug, 'd', 'f', 'https://funder.example/' + slug, region, 'NGO', status, 'Kenya, Rwanda',
             '2020-01-01 00:00:00'))   # created_at is old on purpose: the "new" filter must use the posted date
    conn.commit(); conn.close()


@pytest.fixture(scope='module')
def client():
    seed()
    c = appmod.app.test_client()
    with c.session_transaction() as s:
        s['authenticated'] = True
    return c


def slugs(client, qs):
    j = client.get('/api/grants?search=UITEST&per_page=100&' + qs).get_json()
    return [g['slug'] for g in j['grants']]


def test_overview_requires_login():
    r = appmod.app.test_client().get('/api/overview')
    assert r.status_code == 401


def test_closing_within(client):
    assert slugs(client, 'closing_within=0') == ['uitest-today']
    assert slugs(client, 'closing_within=3&sort=deadline_asc') == ['uitest-today', 'uitest-3']
    assert slugs(client, 'closing_within=30&sort=deadline_asc') == ['uitest-today', 'uitest-3', 'uitest-10']
    # expired rows never appear in a closing window, even when asking for all statuses
    assert 'uitest-old' not in slugs(client, 'closing_within=30&status=all')


def test_posted_within_uses_posted_date_not_created_at(client):
    assert slugs(client, 'posted_within=7&sort=posted_date_desc') == ['uitest-today', 'uitest-3']
    assert slugs(client, 'posted_within=14&sort=posted_date_desc') == ['uitest-today', 'uitest-3', 'uitest-10']


def test_invalid_windows_are_ignored(client):
    assert len(slugs(client, 'closing_within=abc&posted_within=')) == 4   # active rows only, no filter applied


def test_existing_params_unchanged(client):
    j = client.get('/api/grants?search=UITEST&status=all&per_page=100').get_json()
    assert j['total'] == 5
    j = client.get('/api/grants?search=UITEST&region=Africa').get_json()
    assert {g['slug'] for g in j['grants']} == {'uitest-today', 'uitest-3'}


def test_overview_counts(client):
    o = client.get('/api/overview').get_json()
    assert o['closing_today'] >= 1 and o['closing_3'] >= o['closing_today'] and o['closing_7'] >= o['closing_3']
    assert o['closing_30'] >= o['closing_7']
    assert len(o['closing_by_week']) == 8 and o['closing_by_week'][0] <= o['closing_7'] <= o['closing_30']
    assert sum(r['count'] for r in o['regions']) == o['active']
    assert {'with_apply_url', 'with_size', 'with_deadline', 'with_full_text', 'global_region'} <= set(o['health'])
    names = {r['name'] for r in o['regions']}
    assert {'Africa', 'Asia', 'Global'} <= names
    assert any(c['name'] == 'Rwanda' for c in o['countries'])
    assert isinstance(o['runs'], list) and o['next_scheduled_utc'] == '05:00'
