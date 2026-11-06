/* Grants Iraady — shared shell + helpers. Plain ES2015, no dependencies. */
(function () {
  'use strict';
  var GI = window.GI = {};

  /* ── icons (Lucide-style, 1.5 stroke) ── */
  var P = {
    overview: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    spark: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 17v4M17 19h4"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    tag: '<path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><path d="M7.5 7.5h.01"/>',
    building: '<path d="M4 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16M14 9h5a1 1 0 0 1 1 1v11M3 21h18M8 8h2M8 12h2M8 16h2"/>',
    activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
    moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    x: '<path d="M18 6L6 18M6 6l12 12"/>',
    ext: '<path d="M15 3h6v6M10 14L21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
    right: '<path d="M9 6l6 6-6 6"/>',
    left: '<path d="M15 6l-6 6 6 6"/>',
    back: '<path d="M19 12H5M12 19l-7-7 7-7"/>',
    refresh: '<path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M3 21v-5h5"/>',
    sliders: '<path d="M21 4h-7M10 4H3M21 12h-9M8 12H3M21 20h-5M12 20H3M14 2v4M8 10v4M16 18v4"/>',
    check: '<circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/>',
    alert: '<path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01"/>',
    eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    eyeoff: '<path d="M9.9 4.2A10 10 0 0 1 12 4c6.4 0 10 8 10 8a17 17 0 0 1-2.2 3.2M6.6 6.6A16.6 16.6 0 0 0 2 12s3.6 8 10 8a9.7 9.7 0 0 0 5.4-1.6M2 2l20 20M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    phone: '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
    repeat: '<path d="M17 2l4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 0 1-3 3H3"/>',
    play: '<path d="M6 4l14 8-14 8z"/>',
    inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2M5.5 5.1L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.7 4H7.3a2 2 0 0 0-1.8 1.1z"/>'
  };
  GI.icon = function (n, extra) {
    return '<svg class="i' + (extra ? ' ' + extra : '') + '" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' + (P[n] || '') + '</svg>';
  };

  /* ── small helpers ── */
  GI.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  GI.num = function (n) { return (n == null || isNaN(n)) ? '–' : Number(n).toLocaleString('en-US'); };
  GI.q = function (obj) {
    var u = new URLSearchParams();
    Object.keys(obj).forEach(function (k) { if (obj[k] !== '' && obj[k] != null) u.set(k, obj[k]); });
    return u.toString();
  };
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  GI.fmtDate = function (iso, withYear) {
    if (!iso) return '';
    var p = iso.slice(0, 10).split('-'); if (p.length < 3) return iso;
    return (+p[2]) + ' ' + MON[+p[1] - 1] + (withYear === false ? '' : ' ' + p[0]);
  };
  GI.parseUtc = function (s) {
    if (!s) return null;
    var d = new Date(String(s).indexOf('T') < 0 ? String(s).replace(' ', 'T') + 'Z' : (/Z|[+-]\d\d:?\d\d$/.test(s) ? s : s + 'Z'));
    return isNaN(d) ? null : d;
  };
  GI.fmtStamp = function (s) {
    var d = GI.parseUtc(s); if (!d) return '–';
    var hh = ('0' + d.getUTCHours()).slice(-2), mm = ('0' + d.getUTCMinutes()).slice(-2);
    return d.getUTCDate() + ' ' + MON[d.getUTCMonth()] + ', ' + hh + ':' + mm + ' UTC';
  };
  GI.ago = function (s) {
    var d = GI.parseUtc(s); if (!d) return '';
    var m = Math.round((Date.now() - d.getTime()) / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return m + ' min ago';
    var h = Math.round(m / 60); if (h < 36) return h + ' h ago';
    return Math.round(h / 24) + ' days ago';
  };
  GI.duration = function (a, b) {
    var x = GI.parseUtc(a), y = GI.parseUtc(b); if (!x || !y) return '–';
    var s = Math.max(0, Math.round((y - x) / 1000));
    return s < 60 ? s + ' s' : Math.floor(s / 60) + ' min ' + (s % 60) + ' s';
  };

  /* ── deadlines ── */
  GI.daysLeft = function (iso) {
    if (!iso) return null;
    var p = String(iso).slice(0, 10).split('-'); if (p.length < 3) return null;
    var d = Date.UTC(+p[0], +p[1] - 1, +p[2]), n = new Date();
    return Math.round((d - Date.UTC(n.getUTCFullYear(), n.getUTCMonth(), n.getUTCDate())) / 864e5);
  };
  GI.deadline = function (g) {
    var d = GI.daysLeft(g.deadline_iso);
    if (g.status === 'expired' || (d !== null && d < 0)) return { cls: 'red', text: 'Closed', days: d, past: true };
    if (d === null) return { cls: 'grey', text: 'Rolling', days: null, icon: 'repeat' };
    var t;
    if (d === 0) t = 'Closes today';
    else if (d === 1) t = 'Closes tomorrow';
    else if (d <= 60) t = 'Closes in ' + d + ' days';
    else t = 'Closes in ' + Math.round(d / 30) + ' months';
    return { cls: d <= 3 ? 'red' : d <= 14 ? 'amber' : 'green', text: t, days: d };
  };
  GI.chip = function (g, big) {
    var x = GI.deadline(g);
    return '<span class="chip chip-' + x.cls + (big ? ' chip-lg' : '') + '">' + GI.icon(x.icon || 'clock') + GI.esc(x.text) + '</span>';
  };
  GI.sizeText = function (g) { var s = (g.grant_size || '').trim(); return (!s || s === 'Not Available') ? '' : s; };
  GI.isNew = function (g) {
    var m = /^([A-Za-z]+) (\d{1,2}), (\d{4})$/.exec((g.posted_date || '').trim());
    var d = m ? Date.parse(m[1] + ' ' + m[2] + ', ' + m[3] + ' 00:00:00 UTC') : NaN;
    if (isNaN(d)) { var c = GI.parseUtc(g.created_at); d = c ? c.getTime() : NaN; }
    return !isNaN(d) && (Date.now() - d) <= 7 * 864e5;
  };

  /* ── safe HTML for scraped grant text ── */
  GI.sanitize = function (html) {
    html = String(html || '');
    if (!/<[a-z][\s\S]*>/i.test(html)) {
      return html.split(/\n{2,}/).map(function (p) { return p.trim() ? '<p>' + GI.esc(p.trim()).replace(/\n/g, '<br>') + '</p>' : ''; }).join('');
    }
    var doc = new DOMParser().parseFromString('<body>' + html, 'text/html'), body = doc.body;
    body.querySelectorAll('script,style,iframe,object,embed,form,link,meta,base,noscript,svg,math,input,button,textarea,select,img,video,audio,picture,source').forEach(function (n) { n.remove(); });
    body.querySelectorAll('*').forEach(function (el) {
      Array.prototype.slice.call(el.attributes).forEach(function (a) {
        var n = a.name.toLowerCase();
        if (n.indexOf('on') === 0 || n === 'style' || n === 'class' || n === 'id' || n === 'srcset') el.removeAttribute(a.name);
      });
      if (el.tagName === 'A') {
        var h = (el.getAttribute('href') || '').trim();
        if (!/^(https?:\/\/|mailto:)/i.test(h) || /fundsforngo/i.test(h)) {
          while (el.firstChild) el.parentNode.insertBefore(el.firstChild, el);
          el.remove();
        } else {
          el.setAttribute('target', '_blank');
          el.setAttribute('rel', 'noopener noreferrer nofollow');
        }
      }
    });
    return body.innerHTML;
  };

  /* ── data ── */
  GI.get = function (url) {
    return fetch(url, { credentials: 'include' }).then(function (r) {
      if (r.status === 401) { location.href = '/login'; return new Promise(function () {}); }
      if (!r.ok) { var e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
      return r.json();
    });
  };
  var ovP = null;
  GI.overview = function (fresh) {
    if (!ovP || fresh) ovP = GI.get('/api/overview');
    return ovP;
  };

  /* ── theme ── */
  GI.theme = function () { return document.documentElement.getAttribute('data-theme') || 'light'; };
  GI.setTheme = function (t) {
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem('gi-theme', t); } catch (e) {}
  };

  /* ── toast ── */
  GI.toast = function (msg) {
    var t = document.getElementById('toast');
    if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('show');
    clearTimeout(GI._tt); GI._tt = setTimeout(function () { t.classList.remove('show'); }, 2200);
  };

  /* ── shell ── */
  var RADAR = '<svg viewBox="0 0 32 32" aria-hidden="true" focusable="false"><circle cx="16" cy="16" r="14" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="1.5"/><circle cx="16" cy="16" r="8.5" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="1.5"/><path d="M16 16L26 8" stroke="#D9911A" stroke-width="2.4" stroke-linecap="round"/><circle cx="16" cy="16" r="2.4" fill="#D9911A"/></svg>';
  GI.RADAR = RADAR;

  var NAV = [
    { g: 'Discover', items: [
      { k: 'overview', t: 'Overview', i: 'overview', h: '/?view=overview' },
      { k: 'all', t: 'All grants', i: 'list', h: '/?view=all' },
      { k: 'closing', t: 'Closing this week', i: 'clock', h: '/?view=closing', c: 'closing_7', hot: true },
      { k: 'new', t: 'New this week', i: 'spark', h: '/?view=new', c: 'new_7' }
    ] },
    { g: 'Browse by', items: [
      { k: 'region', t: 'Region', i: 'globe', h: '/?view=region' },
      { k: 'category', t: 'Category', i: 'tag', h: '/?view=category' },
      { k: 'funder', t: 'Funder', i: 'building', h: '/?view=funder' }
    ] },
    { g: 'Admin', items: [
      { k: 'health', t: 'Scraper &amp; data health', i: 'activity', h: '/?view=health' }
    ] }
  ];

  GI.mountShell = function (active) {
    var app = document.querySelector('.app'), main = app.querySelector('.main');
    var nav = NAV.map(function (grp) {
      return '<div class="nav-label"><span>' + grp.g + '</span></div>' + grp.items.map(function (it) {
        var plain = it.t.replace(/&amp;/g, '&');
        return '<a href="' + it.h + '" data-k="' + it.k + '" title="' + plain + '"' + (it.k === active ? ' aria-current="page"' : '') + '>' +
          GI.icon(it.i) + '<span class="t">' + it.t + '</span>' + (it.c ? '<span class="cnt" data-c="' + it.c + '" aria-hidden="false"></span>' : '') + '</a>';
      }).join('');
    }).join('');
    var dark = GI.theme() === 'dark';
    var side = document.createElement('aside');
    side.className = 'sidebar'; side.id = 'sidebar'; side.setAttribute('aria-label', 'Main');
    side.innerHTML =
      '<a class="brand" href="/?view=overview" aria-label="Grants Iraady home">' + RADAR + '<span class="brand-txt"><span class="brand-name">Grants Iraady</span><span class="brand-sub">Funding radar</span></span></a>' +
      '<nav class="nav" aria-label="Sections">' + nav + '</nav>' +
      '<div class="side-foot"><div class="upd" id="upd">' + GI.icon('refresh') + '<span><b>Last update</b><span id="upd-t">Loading…</span></span></div>' +
      '<div class="side-actions"><button type="button" class="side-btn icon-only" id="theme-btn" aria-label="' + (dark ? 'Switch to light theme' : 'Switch to dark theme') + '">' + GI.icon(dark ? 'sun' : 'moon') + '</button>' +
      '<a class="side-btn" href="/logout" title="Sign out">' + GI.icon('logout') + '<span class="bt">Sign out</span></a></div></div>';
    app.insertBefore(side, main);

    var mtop = document.createElement('div');
    mtop.className = 'mtop';
    mtop.innerHTML = '<button type="button" id="menu-btn" aria-label="Open menu" aria-expanded="false" aria-controls="sidebar">' + GI.icon('menu') + '</button>' +
      '<a class="brand" href="/?view=overview">' + RADAR + '<span class="brand-name">Grants Iraady</span></a>';
    main.insertBefore(mtop, main.firstChild);
    var scrim = document.createElement('div'); scrim.className = 'scrim'; scrim.id = 'scrim';
    document.body.appendChild(scrim);

    var menuBtn = document.getElementById('menu-btn');
    function setDrawer(open) {
      document.body.classList.toggle('drawer-open', open);
      menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      menuBtn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
      if (open) { var a = side.querySelector('a[aria-current=page]') || side.querySelector('.nav a'); a && a.focus(); } else if (document.activeElement && side.contains(document.activeElement)) menuBtn.focus();
    }
    menuBtn.addEventListener('click', function () { setDrawer(!document.body.classList.contains('drawer-open')); });
    scrim.addEventListener('click', function () { setDrawer(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && document.body.classList.contains('drawer-open')) setDrawer(false); });
    window.addEventListener('resize', function () { if (innerWidth >= 720) document.body.classList.remove('drawer-open'); });

    document.getElementById('theme-btn').addEventListener('click', function () {
      var t = GI.theme() === 'dark' ? 'light' : 'dark'; GI.setTheme(t);
      this.innerHTML = GI.icon(t === 'dark' ? 'sun' : 'moon');
      this.setAttribute('aria-label', t === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
    });

    GI.overview().then(function (o) {
      side.querySelectorAll('[data-c]').forEach(function (el) {
        var v = o[el.getAttribute('data-c')]; el.textContent = GI.num(v);
        if (el.parentNode.getAttribute('data-k') === 'closing' && v > 0) el.classList.add('hot');
      });
      var s = o.last_success || o.last_grant_added;
      document.getElementById('upd-t').innerHTML = s ? GI.esc(GI.fmtStamp(s)) + '<br>' + GI.esc(GI.ago(s)) : 'No run yet';
    }).catch(function () { document.getElementById('upd-t').textContent = 'Unavailable'; });

    fetch('/api/scraper-status', { credentials: 'include' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (s) {
      if (s && s.running) {
        var a = side.querySelector('[data-k=health]');
        if (a && !a.querySelector('.dot-live')) { var d = document.createElement('span'); d.className = 'dot-live'; d.title = 'Scraper running'; a.appendChild(d); }
      }
    }).catch(function () {});
  };
})();
