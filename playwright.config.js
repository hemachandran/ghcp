const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: 'tests',
  timeout: 120000,
  expect: {
    timeout: 10000
  },
  fullyParallel: false,
  workers: 1,
  use: {
    browserName: 'chromium',
    headless: true,
    viewport: { width: 1280, height: 720 },
    baseURL: 'http://127.0.0.1:3000',
    ignoreHTTPSErrors: true,
    actionTimeout: 0,
    navigationTimeout: 120000,
    launchOptions: {
      args: ['--disable-dev-shm-usage']
    }
  },
  webServer: {
    command: 'python3 -m http.server 3000',
    port: 3000,
    reuseExistingServer: true,
    timeout: 120000
  }
});
