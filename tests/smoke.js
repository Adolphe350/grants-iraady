// Smoke test for the Grants Iraady UI. Needs playwright-core and a running server.
//   BASE=http://127.0.0.1:5112 PW=<site password> node tests/smoke.js
// Checks: every page loads, login works (and rejects a wrong password), no console errors / failed requests,
// no sideways scroll at 390px, list filters + pagination + detail + drawer work.
const { chromium } = require('playwright-core');
const BASE = process.env.BASE || 'http://127.0.0.1:5112';
const PASS = process.env.PW || '';
const fails = [];
let checks = 0;
const ok = (cond, msg) => { checks++; if (!cond) { fails.push(msg); console.log('  FAIL ' + msg); } };

(async () => {
  const browser = await chromium.launch();
  for (const [name, vp] of [['desktop 1440x900', { width: 1440, height: 900 }], ['mobile 390x844', { width: 390, height: 844 }]]) {
    console.log('== ' + name);
    const mobile = vp.width < 720;
    const ctx = await browser.newContext({ viewport: vp });
    const page = await ctx.newPage();
    const problems = [];
    page.on('console', m => { if (m.type() === 'error') problems.push('console: ' + m.text()); });
    page.on('pageerror', e => problems.push('pageerror: ' + e.message));
    page.on('response', r => { if (r.url().startsWith(BASE) && r.status() >= 400 && !/\/login$/.test(r.url())) problems.push(r.status() + ' ' + r.url()); });
    const overflow = async (label) => {
      const w = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
      ok(w[0] <= w[1], label + ' has sideways scroll (' + w[0] + ' > ' + w[1] + ')');
    };
    const settle = () => page.waitForLoadState('networkidle').then(() => page.waitForTimeout(250));

    // login page + wrong password
    await page.goto(BASE + '/login'); await settle();
    ok(await page.locator('input[name=password]').count() === 1, 'login form present');
    ok((await page.locator('#s-active').innerText()) !== '–', 'login radar shows real active count');
    await overflow('login');
    await page.fill('input[name=password]', 'definitely-wrong');
    await Promise.all([page.waitForNavigation(), page.click('button[type=submit]')]);
    ok(await page.locator('.error[role=alert]').count() === 1, 'wrong password shows an error');
    await page.fill('input[name=password]', PASS);
    await Promise.all([page.waitForNavigation(), page.click('button[type=submit]')]);
    await settle();
    ok(new URL(page.url()).pathname === '/', 'login redirects to /');

    // every view
    for (const v of ['overview', 'all', 'closing', 'new', 'region', 'category', 'funder', 'health']) {
      await page.goto(BASE + '/?view=' + v); await settle();
      ok((await page.locator('h1').first().innerText()).length > 0, v + ': has a heading');
      ok(await page.locator('#main[aria-busy=false]').count() === 1, v + ': finished loading');
      ok(await page.locator('.nav a[aria-current=page][data-k=' + v + ']').count() === 1, v + ': sidebar marks it current');
      await overflow(v);
    }

    // list: rows, search, filter, pagination, open detail
    await page.goto(BASE + '/?view=all'); await settle();
    const rows = await page.locator('.row .ttl').count();
    ok(rows >= 10, 'list shows rows (' + rows + ')');
    const total0 = await page.locator('#count b').innerText();
    await page.fill('#q', 'health'); await page.waitForTimeout(700); await settle();
    const total1 = await page.locator('#count b').innerText();
    ok(total0 !== total1, 'search changes the result count (' + total0 + ' -> ' + total1 + ')');
    ok(await page.locator('.pill').count() >= 1, 'active-filter pill appears');
    await page.click('#clear-all, .pill'); await settle();
    if (mobile) { await page.click('#tb-toggle'); }
    await page.selectOption('#f-category', { index: 2 }); await settle();
    ok(await page.locator('.pill').count() >= 1, 'category filter adds a pill');
    await page.selectOption('#f-category', ''); await settle();
    if (await page.locator('.pager [data-p="2"]').count()) {
      await page.click('.pager [data-p="2"]'); await settle();
      ok(new URL(page.url()).searchParams.get('page') === '2', 'pagination updates the URL');
    } else ok(false, 'pagination has a page 2');
    await page.goto(BASE + '/?view=closing&days=3'); await settle();
    ok(await page.locator('.row .ttl').count() > 0, 'closing window lists grants');
    await overflow('closing list');
    await page.locator('.row .ttl').first().click(); await settle();
    ok(page.url().includes('/grant/'), 'row opens the grant detail');
    ok(await page.locator('h1').count() === 1, 'detail has a title');
    const apply = await page.locator('a.btn-primary[target=_blank]').first().getAttribute('href').catch(() => null);
    ok(!apply || (/^https?:\/\//.test(apply) && !/fundsforngo/i.test(apply)), 'Apply link goes to a non-FFN https page');
    await overflow('detail');

    // mobile drawer
    if (mobile) {
      await page.goto(BASE + '/?view=overview'); await settle();
      ok(!(await page.locator('#sidebar').isVisible()), 'drawer is hidden by default');
      await page.click('#menu-btn');
      ok(await page.locator('#sidebar').isVisible(), 'hamburger opens the drawer');
      await page.keyboard.press('Escape');
      await page.waitForTimeout(400);
      ok(!(await page.locator('#sidebar').isVisible()), 'Escape closes the drawer');
    }

    // public pages and endpoints (no login needed)
    const anon = await browser.newContext({ viewport: vp }); const ap = await anon.newPage();
    for (const [path, expect] of [['/account-deletion', 'Delete Your Account'], ['/fundnest/privacy', 'Privacy Policy']]) {
      const r = await ap.goto(BASE + path); ok(r.status() === 200, path + ' returns 200');
      ok((await ap.locator('h1').innerText()).includes(expect), path + ' heading');
      const w = await ap.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
      ok(w[0] <= w[1], path + ' has no sideways scroll');
    }
    ok((await ap.goto(BASE + '/healthz')).status() === 200, '/healthz 200');
    ok((await ap.goto(BASE + '/api/public/v1/stats')).status() === 200, 'public stats 200');
    const redir = await ap.goto(BASE + '/'); ok(new URL(ap.url()).pathname === '/login', '/ redirects anonymous users to /login');
    await anon.close();

    ok(problems.length === 0, 'no console errors or failed requests: ' + problems.slice(0, 5).join(' | '));
    await ctx.close();
  }
  await browser.close();
  console.log('\n' + (checks - fails.length) + '/' + checks + ' checks passed');
  process.exit(fails.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
