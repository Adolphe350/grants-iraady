/* Grants Iraady — views for "/" : overview, grant lists, browse-by, scraper & data health. */
(function () {
  'use strict';
  var GI = window.GI, esc = GI.esc, icon = GI.icon, num = GI.num;
  var main = document.getElementById('main');
  var qs = new URLSearchParams(location.search);
  var VIEWS = ['overview', 'all', 'closing', 'new', 'region', 'category', 'funder', 'health'];
  var view = VIEWS.indexOf(qs.get('view')) >= 0 ? qs.get('view') : 'overview';
  var TITLES = { overview: 'Overview', all: 'All grants', closing: 'Closing this week', 'new': 'New this week', region: 'Browse by region', category: 'Browse by category', funder: 'Browse by funder', health: 'Scraper & data health' };
  document.title = TITLES[view] + ' · Grants Iraady';
  GI.mountShell(view);

  function done() { main.setAttribute('aria-busy', 'false'); }
  function head(h, p, right) {
    return '<div class="page-head"><div><h1>' + esc(h) + '</h1>' + (p ? '<p>' + p + '</p>' : '') + '</div>' + (right || '') + '</div>';
  }
  function errorBlock(msg, retry) {
    main.innerHTML = '<div class="panel empty"><div class="art">' + icon('alert') + '</div><h3>Could not load this view</h3><p>' + esc(msg || 'The server did not answer.') + '</p><button class="btn btn-primary" id="retry" type="button">' + icon('refresh') + 'Try again</button></div>';
    document.getElementById('retry').onclick = retry; done();
  }
  function link(params) { return '/?' + GI.q(params); }
  function miniList(items, mode) {
    if (!items.length) return '<div class="mini-empty">Nothing here right now.</div>';
    return '<ul class="mini">' + items.map(function (g) {
      var posted = (mode === 'new' && g.posted_date) ? 'Posted ' + GI.fmtDate(new Date(Date.parse(g.posted_date + ' UTC')).toISOString(), false) : '';
      var sub = [posted, g.donor || 'Unknown funder', GI.sizeText(g)].filter(Boolean).join(' · ');
      return '<li><a href="/grant/' + encodeURI(g.slug || '') + '"><span class="tt">' + esc(g.title) + '</span><span class="sub">' + esc(sub) + '</span>' + GI.chip(g) + '</a></li>';
    }).join('') + '</ul>';
  }
  function bars(list, max, hrefFn, cls, limit) {
    if (!list.length) return '<div class="mini-empty">No data.</div>';
    var m = max || Math.max.apply(null, list.map(function (x) { return x.count; })) || 1;
    return '<ul class="bars">' + list.slice(0, limit || 999).map(function (x) {
      var inner = '<span class="bn">' + esc(x.name) + '</span><span class="bv">' + num(x.count) + '</span><span class="track"><span class="fill ' + (cls || '') + '" style="width:' + Math.max(1, Math.round(x.count / m * 100)) + '%"></span></span>';
      return '<li>' + (hrefFn ? '<a href="' + hrefFn(x) + '">' + inner + '</a>' : '<div class="bar-row">' + inner + '</div>') + '</li>';
    }).join('') + '</ul>';
  }

  /* ───────────── Overview ───────────── */
  function overview() {
    main.innerHTML = head('Overview', 'Deadline-first view of every open grant.') + '<div class="strip" aria-hidden="true">' + new Array(7).join('<div class="k"><div class="n">&nbsp;</div><div class="l">&nbsp;</div></div>') + '</div>';
    Promise.all([
      GI.overview(),
      GI.get('/api/grants?' + GI.q({ closing_within: 7, sort: 'deadline_asc', per_page: 8 })),
      GI.get('/api/grants?' + GI.q({ posted_within: 7, sort: 'posted_date_desc', per_page: 8 }))
    ]).then(function (r) {
      var o = r[0], cl = r[1], nw = r[2];
      var searchForm = '<form class="field-icon" action="/" method="get" role="search" style="min-width:min(100%,340px)"><input type="hidden" name="view" value="all">' + icon('search') +
        '<label class="sr-only" for="ov-q">Search all grants</label><input class="input" id="ov-q" type="search" name="q" placeholder="Search all grants" autocomplete="off"></form>';
      var sub = num(o.active) + ' open grants from ' + num(o.donors) + ' funders. Last update ' + esc(GI.ago(o.last_success || o.last_grant_added) || 'unknown') + '.';
      var strip = '<div class="strip">' +
        '<a href="' + link({ view: 'all' }) + '"><div class="n">' + num(o.active) + '</div><div class="l">Open grants</div></a>' +
        '<a class="a-red" href="' + link({ view: 'closing', days: 0 }) + '"><div class="n">' + num(o.closing_today) + '</div><div class="l">Close today</div></a>' +
        '<a class="hot" href="' + link({ view: 'closing', days: 3 }) + '"><div class="n">' + num(o.closing_3) + '</div><div class="l">Close within 3 days</div></a>' +
        '<a href="' + link({ view: 'closing', days: 7 }) + '"><div class="n">' + num(o.closing_7) + '</div><div class="l">Close within 7 days</div></a>' +
        '<a class="a-green" href="' + link({ view: 'new' }) + '"><div class="n">' + num(o.new_7) + '</div><div class="l">Posted this week</div></a>' +
        '<a href="' + link({ view: 'funder' }) + '"><div class="n">' + num(o.donors) + '</div><div class="l">Funders</div></a></div>';
      var wk = o.closing_by_week || [], wmax = Math.max.apply(null, wk.concat([1]));
      var labels = ['This wk', '+1 wk', '+2 wk', '+3 wk', '+4 wk', '+5 wk', '+6 wk', '+7 wk'];
      var cols = '<div class="cols">' + wk.map(function (v, i) {
        return '<a class="c" href="' + link({ view: 'closing', days: 7 * i + 6 }) + '" title="' + v + ' close in this window"><span class="v">' + num(v) + '</span><span class="bar" style="height:' + Math.max(2, Math.round(v / wmax * 100)) + '%"></span></a>';
      }).join('') + '</div><div class="cols-lab" aria-hidden="true">' + labels.map(function (l) { return '<span>' + l + '</span>'; }).join('') + '</div>';
      var gl = o.health ? o.health.global_region : 0;
      main.innerHTML = head('Overview', sub, searchForm) + strip +
        '<div class="grid-2" style="margin-bottom:16px">' +
        '<section class="panel" aria-labelledby="h-cl"><div class="panel-head"><h2 id="h-cl">Closing soonest</h2><a href="' + link({ view: 'closing' }) + '">All ' + num(o.closing_7) + ' closing this week</a></div>' + miniList(cl.grants) + '</section>' +
        '<section class="panel" aria-labelledby="h-nw"><div class="panel-head"><h2 id="h-nw">Newly posted</h2><a href="' + link({ view: 'new' }) + '">All ' + num(o.new_7) + ' from this week</a></div>' + miniList(nw.grants, 'new') + '</section></div>' +
        '<section class="panel" style="margin-bottom:16px" aria-labelledby="h-wk"><div class="panel-head"><h2 id="h-wk">Deadlines by week</h2><span class="note" style="margin:0">Next 8 weeks, open grants. Click a bar to list up to that week.</span></div><div class="panel-body">' + cols + '</div></section>' +
        '<div class="grid-3">' +
        '<section class="panel" aria-labelledby="h-ct"><div class="panel-head"><h2 id="h-ct">By category</h2><a href="' + link({ view: 'category' }) + '">All</a></div><div class="panel-body">' + bars(o.categories, 0, function (x) { return link({ view: 'all', category: x.name }); }, '', 8) + '</div></section>' +
        '<section class="panel" aria-labelledby="h-rg"><div class="panel-head"><h2 id="h-rg">By region</h2><a href="' + link({ view: 'region' }) + '">All</a></div><div class="panel-body">' + bars(o.regions, 0, function (x) { return link({ view: 'all', region: x.name }); }, 'amber', 7) +
        '<p class="note">' + num(gl) + ' of ' + num(o.active) + ' open grants are not tied to one region and show as Global.</p></div></section>' +
        '<section class="panel" aria-labelledby="h-sz"><div class="panel-head"><h2 id="h-sz">By grant size</h2></div><div class="panel-body">' + bars(o.sizes, 0, function (x) { return link({ view: 'all', size: x.name }); }, 'green', 8) + '</div></section></div>';
      done();
    }).catch(function (e) { errorBlock(e.message, overview); });
  }

  /* ───────────── Grant list (all / closing / new) ───────────── */
  var FKEYS = [['category', 'Category', 'All categories'], ['region', 'Region', 'All regions'], ['country', 'Country', 'All countries'], ['eligible', 'Who can apply', 'Anyone'], ['size', 'Grant size', 'Any size'], ['donor', 'Funder', 'All funders']];
  var st, opts = null, reqCtl = null, timer = null;

  function stateFromUrl() {
    var s = { q: qs.get('q') || '', sort: qs.get('sort') || '', category: qs.get('category') || '', region: qs.get('region') || '', country: qs.get('country') || '',
      eligible: qs.get('eligible') || '', size: qs.get('size') || '', donor: qs.get('donor') || '', status: qs.get('status') || 'active',
      page: Math.max(1, parseInt(qs.get('page'), 10) || 1), per: [25, 50, 100].indexOf(parseInt(qs.get('per'), 10)) >= 0 ? parseInt(qs.get('per'), 10) : 25,
      days: qs.get('days') === null ? '' : String(Math.max(0, parseInt(qs.get('days'), 10) || 0)) };
    if (view === 'closing' && s.days === '') s.days = '7';
    if (view === 'new' && s.days === '') s.days = '7';
    if (!s.sort) s.sort = view === 'new' ? 'posted_date_desc' : 'deadline_asc';
    return s;
  }
  function defaultSort() { return view === 'new' ? 'posted_date_desc' : 'deadline_asc'; }
  function urlParams() {
    var p = { view: view };
    ['q', 'category', 'region', 'country', 'eligible', 'size', 'donor'].forEach(function (k) { if (st[k]) p[k] = st[k]; });
    if (view === 'all' && st.status !== 'active') p.status = st.status;
    if (st.sort !== defaultSort()) p.sort = st.sort;
    if (view !== 'all') p.days = st.days;
    if (st.page > 1) p.page = st.page;
    if (st.per !== 25) p.per = st.per;
    return p;
  }
  function apiParams() {
    var p = { page: st.page, per_page: st.per, search: st.q, sort: st.sort, category: st.category, region: st.region, country: st.country, eligible: st.eligible, size: st.size, donor: st.donor };
    p.status = view === 'all' ? st.status : 'active';
    if (view === 'closing') p.closing_within = st.days;
    if (view === 'new') p.posted_within = st.days;
    return p;
  }
  function sync() {
    var u = '/?' + GI.q(urlParams());
    history.replaceState(null, '', u);
    try { sessionStorage.setItem('gi-last', u); } catch (e) {}
  }

  function listShell() {
    var windowCtl = '';
    if (view === 'closing') windowCtl = windowSeg('Closes within', [[0, 'Today'], [3, '3 days'], [7, '7 days'], [30, '30 days']]);
    if (view === 'new') windowCtl = windowSeg('Posted in the last', [[3, '3 days'], [7, '7 days'], [14, '14 days'], [30, '30 days']]);
    var sortOpts = [['deadline_asc', 'Deadline: soonest'], ['deadline_desc', 'Deadline: latest'], ['posted_date_desc', 'Newest posted']];
    var subs = { all: 'Search, filter and open any grant.', closing: 'Open grants with a deadline coming up, soonest first.', 'new': 'Grants posted recently, newest first.' };
    main.innerHTML = head(TITLES[view], subs[view]) + windowCtl +
      '<div class="toolbar" id="toolbar" role="search"><div class="tb-row">' +
      '<label class="field-icon">' + icon('search') + '<span class="sr-only">Search grants, funders and topics</span><input class="input" id="q" type="search" placeholder="Search grants, funders, topics" autocomplete="off" value="' + esc(st.q) + '"><kbd aria-hidden="true">/</kbd></label>' +
      '<label><span class="sr-only">Sort by</span><select class="select sort" id="sort">' + sortOpts.map(function (o) { return '<option value="' + o[0] + '"' + (st.sort === o[0] ? ' selected' : '') + '>' + o[1] + '</option>'; }).join('') + '</select></label>' +
      '<button class="btn tb-toggle" id="tb-toggle" type="button" aria-expanded="true" aria-controls="filters">' + icon('sliders') + 'Filters</button></div>' +
      '<div class="filters" id="filters">' + FKEYS.map(function (f) {
        return '<label><span class="lab">' + f[1] + '</span><select class="select" id="f-' + f[0] + '" data-k="' + f[0] + '"><option value="">' + f[2] + '</option></select></label>';
      }).join('') + (view === 'all' ? '<label><span class="lab">Status</span><select class="select" id="f-status" data-k="status"><option value="active">Open</option><option value="expired">Closed</option><option value="all">All</option></select></label>' : '') + '</div>' +
      '<div class="pills" id="pills"></div></div>' +
      '<div class="tb-row" style="margin:0 0 10px"><div class="tb-count" id="count" role="status" aria-live="polite">Loading…</div></div>' +
      '<div class="rows-wrap" id="rows-wrap"></div>' +
      '<p class="kbd-hint"><kbd>/</kbd> search · <kbd>j</kbd> / <kbd>k</kbd> move between grants · <kbd>Enter</kbd> open</p>';
    if (innerWidth < 720) { document.getElementById('filters').hidden = true; document.getElementById('tb-toggle').setAttribute('aria-expanded', 'false'); }
  }
  function windowSeg(label, arr) {
    return '<div class="window"><span id="win-l">' + label + '</span><div class="seg" role="group" aria-labelledby="win-l">' + arr.map(function (a) {
      return '<button type="button" data-days="' + a[0] + '" aria-pressed="' + (String(a[0]) === st.days ? 'true' : 'false') + '">' + a[1] + '</button>';
    }).join('') + '</div></div>';
  }
  function fillOptions() {
    GI.get('/api/filter-options').then(function (d) {
      opts = d;
      var map = { category: d.categories, region: d.regions, country: d.countries, eligible: d.eligible, size: d.sizes, donor: d.donors };
      FKEYS.forEach(function (f) {
        var sel = document.getElementById('f-' + f[0]), list = (map[f[0]] || []).filter(Boolean), cur = st[f[0]];
        if (cur && list.indexOf(cur) < 0) list = [cur].concat(list);
        sel.insertAdjacentHTML('beforeend', list.map(function (v) { return '<option value="' + esc(v) + '">' + esc(v) + '</option>'; }).join(''));
        sel.value = cur; sel.classList.toggle('on', !!cur);
      });
    }).catch(function () {});
    var s = document.getElementById('f-status'); if (s) s.value = st.status;
  }
  function pills() {
    var out = [];
    if (st.q) out.push(['q', 'Search: ' + st.q]);
    FKEYS.forEach(function (f) { if (st[f[0]]) out.push([f[0], f[1] + ': ' + st[f[0]]]); });
    if (view === 'all' && st.status !== 'active') out.push(['status', 'Status: ' + (st.status === 'expired' ? 'Closed' : 'All')]);
    var el = document.getElementById('pills');
    el.innerHTML = out.map(function (p) {
      return '<button type="button" class="pill" data-k="' + p[0] + '" aria-label="Remove filter ' + esc(p[1]) + '">' + esc(p[1]) + '<span class="x">' + icon('x') + '</span></button>';
    }).join('') + (out.length > 1 ? '<button type="button" class="pill-clear" id="clear-all">Clear all</button>' : '');
    var tg = document.getElementById('tb-toggle');
    if (tg) tg.innerHTML = icon('sliders') + 'Filters' + (out.filter(function (p) { return p[0] !== 'q'; }).length ? ' (' + out.filter(function (p) { return p[0] !== 'q'; }).length + ')' : '');
    FKEYS.forEach(function (f) { var s = document.getElementById('f-' + f[0]); if (s) s.classList.toggle('on', !!st[f[0]]); });
    return out.length;
  }

  function skeleton() {
    var r = ''; for (var i = 0; i < 8; i++) r += '<li class="row"><div class="c-dl"><span class="sk" style="width:104px"></span></div><div class="c-main"><span class="sk" style="width:' + (55 + (i * 7) % 35) + '%;margin-bottom:8px"></span><span class="sk" style="width:30%;height:10px"></span></div><div class="c-size"><span class="sk" style="width:110px"></span></div><div class="c-reg"><span class="sk" style="width:70px"></span></div><div></div></li>';
    return '<div class="rows-head" aria-hidden="true"><div>Deadline</div><div>Grant</div><div>Size</div><div class="h-reg">Location</div><div></div></div><ul class="rows skel" aria-hidden="true">' + r + '</ul>';
  }
  function loc(g) {
    var c = (g.countries || '').split(',').map(function (x) { return x.trim(); }).filter(function (x) { return x && x !== 'Global'; });
    if (c.length) return esc(c[0]) + (c.length > 1 ? ' <span style="color:var(--faint)">+' + (c.length - 1) + '</span>' : '');
    return esc(g.region || 'Global');
  }
  function rowHtml(g) {
    var href = '/grant/' + encodeURI(g.slug || ''), d = GI.deadline(g), sz = GI.sizeText(g);
    var dateLine = g.deadline_iso ? GI.fmtDate(g.deadline_iso) : (d.cls === 'grey' ? 'No fixed deadline' : '');
    var meta = '<span class="fund">' + esc(g.donor || 'Unknown funder') + '</span>' + (g.category ? '<span class="sep" aria-hidden="true">·</span><span>' + esc(g.category) + '</span>' : '');
    return '<li class="row' + (d.past ? ' past' : '') + '" data-href="' + href + '">' +
      '<div class="c-dl">' + GI.chip(g) + '<small>' + esc(dateLine) + '</small>' + (GI.isNew(g) && !d.past ? '<span class="chip chip-green" style="height:20px;font-size:11.5px">New</span>' : '') + '</div>' +
      '<div class="c-main"><a class="ttl" href="' + href + '">' + esc(g.title) + '</a><div class="meta">' + meta + '</div></div>' +
      '<div class="c-size' + (sz ? '' : ' na') + '">' + (sz ? esc(sz) : 'Size not stated') + '</div>' +
      '<div class="c-reg">' + loc(g) + '</div><div class="go" aria-hidden="true">' + icon('right') + '</div></li>';
  }
  function pagerHtml(page, pages) {
    if (pages <= 1) return '';
    var nums = [], i;
    for (i = 1; i <= pages; i++) if (i === 1 || i === pages || Math.abs(i - page) <= 1 || (page <= 3 && i <= 4) || (page >= pages - 2 && i >= pages - 3)) nums.push(i);
    var h = '<button type="button" data-p="' + (page - 1) + '"' + (page <= 1 ? ' disabled' : '') + ' aria-label="Previous page">' + icon('left') + '</button>', prev = 0;
    nums.forEach(function (n) {
      if (prev && n - prev > 1) h += '<span class="gap" aria-hidden="true">…</span>';
      h += '<button type="button" data-p="' + n + '"' + (n === page ? ' aria-current="page"' : '') + ' aria-label="Page ' + n + '">' + n + '</button>'; prev = n;
    });
    return h + '<button type="button" data-p="' + (page + 1) + '"' + (page >= pages ? ' disabled' : '') + ' aria-label="Next page">' + icon('right') + '</button>';
  }

  function load() {
    if (reqCtl) reqCtl.abort();
    reqCtl = new AbortController();
    var wrap = document.getElementById('rows-wrap'); wrap.innerHTML = skeleton();
    var n = pills(); sync();
    fetch('/api/grants?' + GI.q(apiParams()), { credentials: 'include', signal: reqCtl.signal }).then(function (r) {
      if (r.status === 401) { location.href = '/login'; return null; }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(function (d) {
      if (!d) return;
      var label = { all: st.status === 'expired' ? 'closed grants' : st.status === 'all' ? 'grants' : 'open grants', closing: 'closing ' + (st.days === '0' ? 'today' : 'within ' + st.days + ' days'), 'new': 'posted in the last ' + st.days + ' days' }[view];
      document.getElementById('count').innerHTML = '<b>' + num(d.total) + '</b> ' + esc(label) + (n ? ' match your filters' : '');
      if (!d.grants.length) {
        wrap.innerHTML = '<div class="empty"><div class="art">' + icon('inbox') + '</div><h3>No grants match</h3><p>' + (n ? 'Try removing a filter or searching for a shorter term.' : 'Nothing in this window right now. Try a wider one.') + '</p>' + (n ? '<button class="btn btn-primary" type="button" id="clear-all">Clear all filters</button>' : '') + '</div>';
        return;
      }
      var from = (d.page - 1) * st.per + 1, to = from + d.grants.length - 1;
      wrap.innerHTML = '<div class="rows-head" aria-hidden="true"><div>Deadline</div><div>Grant</div><div>Size</div><div class="h-reg">Location</div><div></div></div>' +
        '<ul class="rows" id="rows">' + d.grants.map(rowHtml).join('') + '</ul>' +
        '<div class="cardbar"><span class="range">Showing ' + num(from) + '–' + num(to) + ' of ' + num(d.total) + '</span>' +
        '<nav class="pager" aria-label="Pagination">' + pagerHtml(d.page, d.pages) + '</nav>' +
        '<label class="perpage">Per page <select class="select" id="per">' + [25, 50, 100].map(function (v) { return '<option' + (v === st.per ? ' selected' : '') + '>' + v + '</option>'; }).join('') + '</select></label></div>';
    }).catch(function (e) {
      if (e.name === 'AbortError') return;
      wrap.innerHTML = '<div class="empty"><div class="art">' + icon('alert') + '</div><h3>Could not load grants</h3><p>' + esc(e.message) + '</p><button class="btn btn-primary" type="button" id="retry-l">' + icon('refresh') + 'Try again</button></div>';
    });
  }

  function list() {
    st = stateFromUrl(); listShell(); fillOptions(); load(); done();
    var q = document.getElementById('q');
    q.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { st.q = q.value.trim(); st.page = 1; load(); }, 300); });
    document.getElementById('sort').addEventListener('change', function (e) { st.sort = e.target.value; st.page = 1; load(); });
    document.getElementById('filters').addEventListener('change', function (e) { var k = e.target.getAttribute('data-k'); if (!k) return; st[k] = e.target.value; st.page = 1; load(); });
    var tg = document.getElementById('tb-toggle');
    tg.addEventListener('click', function () { var f = document.getElementById('filters'); f.hidden = !f.hidden; tg.setAttribute('aria-expanded', f.hidden ? 'false' : 'true'); });
    main.addEventListener('click', function (e) {
      var t = e.target.closest('button, .row, a'); if (!t) return;
      if (t.classList.contains('pill')) { var k = t.getAttribute('data-k'); if (k === 'q') { st.q = ''; q.value = ''; } else if (k === 'status') { st.status = 'active'; document.getElementById('f-status').value = 'active'; } else { st[k] = ''; document.getElementById('f-' + k).value = ''; } st.page = 1; load(); }
      else if (t.id === 'clear-all') { FKEYS.forEach(function (f) { st[f[0]] = ''; document.getElementById('f-' + f[0]).value = ''; }); st.q = ''; q.value = ''; st.status = 'active'; var fs = document.getElementById('f-status'); if (fs) fs.value = 'active'; st.page = 1; load(); }
      else if (t.id === 'retry-l') load();
      else if (t.hasAttribute('data-p')) { st.page = parseInt(t.getAttribute('data-p'), 10); load(); document.getElementById('toolbar').scrollIntoView({ block: 'start' }); }
      else if (t.hasAttribute('data-days')) { st.days = t.getAttribute('data-days'); st.page = 1; main.querySelectorAll('[data-days]').forEach(function (b) { b.setAttribute('aria-pressed', b === t ? 'true' : 'false'); }); load(); }
      else if (t.classList.contains('row') && !e.target.closest('a')) { location.href = t.getAttribute('data-href'); }
    });
    main.addEventListener('change', function (e) { if (e.target.id === 'per') { st.per = parseInt(e.target.value, 10); st.page = 1; load(); } });
    document.addEventListener('keydown', function (e) {
      var tag = (document.activeElement && document.activeElement.tagName) || '';
      var typing = /INPUT|SELECT|TEXTAREA/.test(tag);
      if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey) { e.preventDefault(); q.focus(); q.select(); return; }
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === 'j' || e.key === 'k') {
        var links = Array.prototype.slice.call(main.querySelectorAll('.row .ttl')); if (!links.length) return;
        var i = links.indexOf(document.activeElement); i = e.key === 'j' ? Math.min(links.length - 1, i + 1) : Math.max(0, i < 0 ? 0 : i - 1);
        links[i].focus(); e.preventDefault();
      }
    });
  }

  /* ───────────── Browse by ───────────── */
  function browse() {
    var rt = { region: 'Region', category: 'Category', funder: 'Funder' };
    main.innerHTML = head(TITLES[view], 'Pick one to see its open grants.');
    GI.overview().then(function (o) {
      var h = '';
      if (view === 'category') {
        h = '<section class="panel" style="max-width:760px"><div class="panel-head"><h2>' + o.categories.length + ' categories</h2><span class="note" style="margin:0">Open grants</span></div><div class="panel-body">' + bars(o.categories, 0, function (x) { return link({ view: 'all', category: x.name }); }) + '</div></section>';
      } else if (view === 'region') {
        h = '<div class="browse-grid"><section class="panel"><div class="panel-head"><h2>Regions</h2><span class="note" style="margin:0">Open grants</span></div><div class="panel-body">' + bars(o.regions, 0, function (x) { return link({ view: 'all', region: x.name }); }, 'amber') +
          '<p class="note">Most grants name no single region and are labelled Global. Use Country for a closer match.</p></div></section>' +
          '<section class="panel"><div class="panel-head"><h2>Countries named in grants</h2><span class="note" style="margin:0" id="cn-n"></span></div><div class="panel-body" id="cn"></div></section></div>';
      } else {
        h = '<section class="panel" style="max-width:760px"><div class="panel-head"><h2>' + num(o.donor_counts.length) + ' funders with open grants</h2></div><div class="panel-body"><label class="field-icon list-search">' + icon('search') + '<span class="sr-only">Filter funders by name</span><input class="input" id="fs" type="search" placeholder="Filter funders" autocomplete="off"></label><div id="fl"></div></div></section>';
      }
      main.innerHTML = head(TITLES[view], 'Pick one to see its open grants.') + h; done();
      if (view === 'region') {
        var shown = 20, cn = document.getElementById('cn');
        var draw = function () {
          cn.innerHTML = bars(o.countries, 0, function (x) { return link({ view: 'all', country: x.name }); }, '', shown) +
            (shown < o.countries.length ? '<button type="button" class="btn btn-sm" id="more" style="margin-top:10px">Show all ' + o.countries.length + ' countries</button>' : '');
          document.getElementById('cn-n').textContent = o.countries.length + ' countries';
          var m = document.getElementById('more'); if (m) m.onclick = function () { shown = 999; draw(); };
        };
        draw();
      }
      if (view === 'funder') {
        var fl = document.getElementById('fl'), fs = document.getElementById('fs'), lim = 40, cur = o.donor_counts, mx = cur.length ? cur[0].count : 1;
        var drawF = function () {
          var needle = fs.value.trim().toLowerCase();
          cur = needle ? o.donor_counts.filter(function (x) { return x.name.toLowerCase().indexOf(needle) >= 0; }) : o.donor_counts;
          fl.innerHTML = cur.length ? bars(cur, mx, function (x) { return link({ view: 'all', donor: x.name }); }, '', lim) +
            (lim < cur.length ? '<button type="button" class="btn btn-sm" id="more" style="margin-top:10px">Show 40 more (' + num(cur.length - lim) + ' left)</button>' : '') : '<div class="mini-empty">No funder matches “' + esc(fs.value) + '”.</div>';
          var m = document.getElementById('more'); if (m) m.onclick = function () { lim += 40; drawF(); m = null; document.getElementById('fs').focus(); };
        };
        fs.addEventListener('input', function () { lim = 40; drawF(); });
        drawF();
      }
    }).catch(function (e) { errorBlock(e.message, browse); });
  }

  /* ───────────── Scraper & data health ───────────── */
  var poll = null, prevStart = null, clickedAt = 0;
  function health() {
    main.innerHTML = head('Scraper & data health', 'The scraper copies new grants from the Funds for NGOs member site once a day.') + '<div class="panel" style="padding:24px"><span class="sk" style="width:40%"></span></div>';
    Promise.all([GI.overview(true), GI.get('/api/scraper-status')]).then(function (r) { drawHealth(r[0], r[1]); done(); }).catch(function (e) { errorBlock(e.message, health); });
  }
  function pct(a, b) { return b ? Math.round(a / b * 100) : 0; }
  function drawHealth(o, s) {
    var running = !!s.running, failed = !running && s.status === 'failed', never = s.status === 'never';
    var lamp = running ? 'run' : failed ? 'fail' : '';
    var title = running ? 'Scraper is running' : failed ? 'Last run failed' : never ? 'No run yet' : 'Up to date';
    var msg = s.message || (never ? 'Run the scraper to fetch grants.' : '');
    var h = o.health || {}, act = o.active || 0;
    function cov(label, v, note, soft) { var p = pct(v, act); return '<div class="cov-i"><div class="top"><span>' + label + '</span><b>' + num(v) + ' of ' + num(act) + ' · ' + p + '%</b></div><div class="track"><span class="fill' + (soft ? ' mid' : p < 50 ? ' low' : p < 90 ? ' mid' : '') + '" style="width:' + p + '%"></span></div>' + (note ? '<small>' + note + '</small>' : '') + '</div>'; }
    var runs = (o.runs || []).map(function (r) {
      var c = r.status === 'success' ? 'green' : r.status === 'failed' ? 'red' : 'amber';
      return '<tr><td class="num">#' + r.id + '</td><td>' + esc(GI.fmtStamp(r.started_at)) + '</td><td>' + esc(r.finished_at ? GI.duration(r.started_at, r.finished_at) : '–') + '</td><td>' + esc(r.trigger || '–') + '</td><td class="r num">' + num(r.fetched) + '</td><td class="r num">' + num(r.added) + '</td><td><span class="chip chip-' + c + '">' + esc(r.status || '–') + '</span></td><td class="msg">' + esc(r.message || '') + '</td></tr>';
    }).join('');
    main.innerHTML = head('Scraper & data health', 'The scraper copies new grants from the Funds for NGOs member site once a day.') +
      '<div class="stack"><section class="panel" aria-labelledby="rs-h"><div class="runstate"><div class="lamp ' + lamp + '">' + (running ? '<span class="spin"></span>' : icon(failed ? 'alert' : 'check')) + '</div>' +
      '<div class="rs-main"><h2 id="rs-h">' + title + '</h2><p id="rs-msg" role="status">' + esc(msg) + (running && s.fetched ? ' · scanned ' + s.fetched : '') + '</p></div>' +
      '<button class="btn btn-primary btn-lg" id="run" type="button"' + (running ? ' disabled' : '') + '>' + (running ? '<span class="spin"></span>Scraping…' : icon('refresh') + 'Run scraper now') + '</button></div>' +
      '<dl class="facts"><div><dt>Last success</dt><dd>' + esc(GI.fmtStamp(o.last_success)) + '<small style="display:block;color:var(--muted);font-weight:500">' + esc(GI.ago(o.last_success)) + '</small></dd></div>' +
      '<div><dt>Last run added</dt><dd>' + (o.runs && o.runs[0] ? num(o.runs[0].added) + ' grants' : '–') + '</dd></div>' +
      '<div><dt>Next scheduled run</dt><dd>Daily, 05:00 UTC</dd></div>' +
      '<div><dt>Grants in database</dt><dd>' + num(o.total) + ' <small style="color:var(--muted);font-weight:500">(' + num(o.expired) + ' closed)</small></dd></div></dl></section>' +
      '<section class="panel" aria-labelledby="cv-h"><div class="panel-head"><h2 id="cv-h">Data coverage, open grants</h2></div><div class="panel-body"><div class="cov">' +
      cov('Funder’s own apply link', h.with_apply_url, 'Apply always opens the funder’s page, never Funds for NGOs.') + cov('Full text', h.with_full_text) + cov('Deadline date', h.with_deadline, 'Grants without a date show as Rolling.') + cov('Grant size stated', h.with_size, 'The rest show “Size not stated”.') + cov('Specific region', act - (h.global_region || 0), 'The source rarely names one region, so most grants read Global.', true) +
      '</div></div></section>' +
      '<section class="panel" aria-labelledby="rn-h"><div class="panel-head"><h2 id="rn-h">Recent runs</h2><span class="note" style="margin:0">Times in UTC</span></div><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Run</th><th>Started</th><th>Took</th><th>Trigger</th><th class="r">Scanned</th><th class="r">Added</th><th>Result</th><th>Message</th></tr></thead><tbody>' + (runs || '<tr><td colspan="8" class="msg">No runs recorded yet.</td></tr>') + '</tbody></table></div></section></div>';
    var btn = document.getElementById('run');
    btn.onclick = function () {
      prevStart = s.started_at || null; clickedAt = Date.now();
      btn.disabled = true; btn.innerHTML = '<span class="spin"></span>Starting…';
      fetch('/api/run-scraper', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: '{}' })
        .then(function (r) { return r.json().then(function (d) { return { st: r.status, d: d }; }); })
        .then(function (r) {
          if (r.st === 401) { location.href = '/login'; return; }
          if (r.st !== 409 && !r.d.ok) { GI.toast('Could not start: ' + (r.d.error || 'unknown error')); btn.disabled = false; btn.innerHTML = icon('refresh') + 'Run scraper now'; return; }
          if (r.st === 409) prevStart = '__running__';
          startPoll();
        }).catch(function () { GI.toast('Could not reach the server.'); btn.disabled = false; btn.innerHTML = icon('refresh') + 'Run scraper now'; });
    };
    if (running) { prevStart = '__running__'; startPoll(); }
  }
  function startPoll() {
    clearInterval(poll);
    var tick = function () {
      GI.get('/api/scraper-status').then(function (s) {
        var starting = !s.running && prevStart !== '__running__' && s.started_at === prevStart && Date.now() - clickedAt < 30000;
        if (s.running || starting) {
          var p = document.getElementById('rs-msg'); if (p) p.textContent = (s.running ? (s.message || 'Scraping…') + (s.fetched ? ' · scanned ' + s.fetched : '') : 'Starting…');
          var b = document.getElementById('run'); if (b && !b.disabled) b.disabled = true;
          return;
        }
        clearInterval(poll); prevStart = null;
        GI.overview(true).then(function (o) { drawHealth(o, s); });
      }).catch(function () {});
    };
    tick(); poll = setInterval(tick, 3000);
  }

  ({ overview: overview, all: list, closing: list, 'new': list, region: browse, category: browse, funder: browse, health: health })[view]();
})();
