#!/usr/bin/env node
// Real browser acceptance: local HTTP fixture, form interaction, screenshot and trace.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');

function fail(message) { throw new Error(message); }
function parseArgs(argv) {
  const options = {};
  for (let i = 0; i < argv.length; i += 2) {
    if (!['--state', '--runtime', '--browser'].includes(argv[i]) || !argv[i + 1]) fail('Use --state NEW_ABSOLUTE_DIR [--runtime ABSOLUTE_RUNTIME] [--browser ABSOLUTE_EXECUTABLE]');
    options[argv[i].slice(2)] = argv[i + 1];
  }
  return options;
}
function noSymlinkParents(p) {
  if (!path.isAbsolute(p) || path.normalize(p) !== p) fail('Paths must be absolute and normalized');
  for (let current = p; current !== path.dirname(current); current = path.dirname(current)) {
    if (fs.existsSync(current) && fs.lstatSync(current).isSymbolicLink()) fail('Refusing symlink in output path');
  }
}
function sha(file) { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'); }

(async () => {
  if (process.argv.slice(2).some(arg => ['--help', '-h'].includes(arg))) {
    process.stdout.write('Usage: agentic-browser-smoke --state NEW_ABSOLUTE_DIR [--browser APPROVED_ABSOLUTE_BROWSER]\nRun real local UI acceptance with Chromium sandboxing enabled.\n');
    return;
  }
  const args = parseArgs(process.argv.slice(2));
  const runtime = args.runtime || path.resolve(__dirname, '..');
  const browserFile = args.browser || process.env.AGENTIC_CHROMIUM_EXECUTABLE || path.join(runtime, 'browser/usr/lib/chromium/chromium');
  if (!args.state) fail('--state is required');
  noSymlinkParents(args.state);
  if (fs.existsSync(args.state)) fail('Preserving existing state; use a new output directory');
  if (!path.isAbsolute(browserFile) || !fs.statSync(browserFile).isFile()) fail('A qualified native browser executable is required');
  const { chromium } = require(path.join(runtime, 'node_modules/playwright'));
  fs.mkdirSync(args.state, { recursive: true, mode: 0o700 });
  let server, browser, context;
  const result = { schemaVersion: 1, passed: false, playwrightVersion: require(path.join(runtime, 'node_modules/playwright/package.json')).version,
    browserExecutable: browserFile, browserSha256: sha(browserFile), chromiumSandbox: true,
    checksRequested: ['local HTTP navigation', 'accessible form interaction', 'DOM result', 'PNG screenshot', 'Playwright trace'],
    checksCompleted: [],
    externalRequests: [] };
  try {
    server = http.createServer((request, response) => {
      response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      response.end('<!doctype html><html lang="en"><meta charset="utf-8"><title>Offline browser qualification</title><style>body{font:18px sans-serif;margin:3rem}button,input{font:inherit;padding:.5rem}output{display:block;margin:2rem 0}</style><main><h1>Offline browser qualification</h1><label>Project name <input id="project" value=""></label><button id="create">Create task</button><output id="result" role="status">No task yet</output></main><script>document.querySelector("#create").onclick=()=>{document.querySelector("#result").textContent="Ready: "+document.querySelector("#project").value}</script></html>');
    });
    await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
    const origin = 'http://127.0.0.1:' + server.address().port;
    browser = await chromium.launch({ executablePath: browserFile, headless: true, chromiumSandbox: true, timeout: 30000 });
    result.browserVersion = browser.version();
    result.checksCompleted.push('browser launch');
    context = await browser.newContext({ viewport: { width: 1000, height: 700 }, locale: 'en-US', timezoneId: 'UTC', serviceWorkers: 'block' });
    await context.route('**/*', async route => {
      const url = route.request().url();
      if (url.startsWith(origin + '/')) return route.continue();
      result.externalRequests.push(url);
      return route.abort('blockedbyclient');
    });
    await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
    const page = await context.newPage();
    await page.goto(origin + '/fixture', { waitUntil: 'networkidle', timeout: 15000 });
    if (await page.title() !== 'Offline browser qualification') fail('Unexpected title');
    result.checksCompleted.push('local HTTP navigation');
    await page.getByLabel('Project name').fill('Disconnected delivery');
    await page.getByRole('button', { name: 'Create task' }).click();
    if (await page.getByRole('status').innerText() !== 'Ready: Disconnected delivery') fail('UI interaction failed');
    result.checksCompleted.push('accessible form interaction', 'DOM result');
    const screenshot = path.join(args.state, 'browser-smoke.png');
    await page.screenshot({ path: screenshot, fullPage: true });
    const trace = path.join(args.state, 'browser-trace.zip');
    await context.tracing.stop({ path: trace });
    result.screenshot = { file: screenshot, sha256: sha(screenshot) };
    result.trace = { file: trace, sha256: sha(trace) };
    result.checksCompleted.push('PNG screenshot', 'Playwright trace');
    if (result.externalRequests.length) fail('Fixture attempted an unexpected network request');
    result.passed = true;
  } catch (error) {
    result.error = String(error && error.message || error);
  } finally {
    if (context) await context.close().catch(() => {});
    if (browser) await browser.close().catch(() => {});
    if (server) await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(args.state, 'qualification.json'), JSON.stringify(result, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
  }
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  process.exitCode = result.passed ? 0 : 1;
})().catch(error => { process.stderr.write(String(error.message || error) + '\n'); process.exitCode = 2; });
