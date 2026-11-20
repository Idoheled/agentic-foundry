'use strict';
// Copy this project config or import these settings into the existing project config.
// The qualified launcher exports the runtime and browser paths for this process.
const path = require('node:path');
const runtime = process.env.AGENTIC_PLAYWRIGHT_ROOT;
if (!runtime) throw new Error('Run this config through agentic-playwright or provide AGENTIC_PLAYWRIGHT_ROOT');
const { defineConfig } = require(path.join(runtime, 'node_modules/@playwright/test'));
const browser = process.env.AGENTIC_CHROMIUM_EXECUTABLE || path.join(runtime, 'browser/usr/lib/chromium/chromium');
module.exports = defineConfig({
  testDir: './tests/browser',
  timeout: 30000,
  forbidOnly: true,
  retries: 0,
  workers: 2,
  reporter: 'list',
  use: {
    browserName: 'chromium',
    headless: true,
    launchOptions: { executablePath: browser, chromiumSandbox: true },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
