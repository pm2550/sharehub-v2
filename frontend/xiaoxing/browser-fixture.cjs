// Headless-browser harness shared by the nod atlas build scripts.
//
// Requires Playwright to be installed in the environment running the build:
//   npm install playwright && npx playwright install chromium
//
// Paths are resolved relative to this file so the scripts work from a plain
// checkout. The fixture serves the local app at 127.0.0.1:8090, substituting
// this directory's static assets and avatar controls so the atlas can be
// composited without touching the production install.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const root = __dirname;

const launch = () =>
  chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  });

async function routes(context, live = false) {
  await context.route('http://127.0.0.1:8090/**', async (r) => {
    const q = r.request();
    const u = new URL(q.url());
    if (q.method() !== 'GET') return r.abort();
    if (live) return r.continue();
    if (u.pathname.startsWith('/static/')) {
      const f = path.join(root, u.pathname);
      if (fs.existsSync(f)) return r.fulfill({ path: f });
    }
    if (q.resourceType() === 'document') {
      const response = await r.fetch();
      let html = await response.text();
      const controls = fs.readFileSync(path.join(root, 'templates', '_avatar.html'), 'utf8').split('<div class="avatar-controls"')[1];
      html = html.replace(/<div class="avatar-controls"[^]*?<\/div>/, '<div class="avatar-controls"' + controls.trim());
      return r.fulfill({ response, body: html });
    }
    return r.continue();
  });
}

module.exports = { launch, routes, root };
