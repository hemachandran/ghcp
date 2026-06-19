const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const PERFORMANCE_BUDGETS = {
  ttfb: 800,
  fcp: 1800,
  lcp: 2500,
  cls: 0.10,
  inp: 200,
  payloadMb: 2.0
};

const targetUrl = process.env.PERFORMANCE_URL || '/performance-test.html';
const outputFileName = process.env.PERFORMANCE_OUTPUT || 'performance-metrics.json';
const outputFile = path.join(__dirname, '..', 'test-results', outputFileName);
const isExternalTarget = targetUrl.startsWith('http');

function writeReport(report) {
  const dir = path.dirname(outputFile);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(outputFile, JSON.stringify(report, null, 2));
}

async function configureThrottling(cdp) {
  await cdp.send('Network.enable');
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  await cdp.send('Network.emulateNetworkConditions', {
    offline: false,
    latency: 150,
    downloadThroughput: (1.6 * 1024 * 1024) / 8,
    uploadThroughput: (750 * 1024) / 8,
    connectionType: 'cellular4g'
  });
}

function collectResponsePayload(page) {
  let totalPayloadSize = 0;
  page.on('response', (response) => {
    const header = response.headers()['content-length'];
    if (header) {
      const value = parseInt(header, 10);
      if (!Number.isNaN(value)) {
        totalPayloadSize += value;
      }
    }
  });
  return () => totalPayloadSize;
}

test.describe('Agent Skills performance', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      if (!window.__perf) {
        window.__perf = { inp: 0 };
      }

      new PerformanceObserver((entries) => {
        for (const entry of entries.getEntries()) {
          if (entry.duration > window.__perf.inp) {
            window.__perf.inp = entry.duration;
          }
        }
      }).observe({ type: 'event', buffered: true, durationThreshold: 0 });
    });
  });

  test('validates performance metrics against industry budgets', async ({ page, context }) => {
    const cdp = await context.newCDPSession(page);
    await configureThrottling(cdp);
    const getPayloadSize = collectResponsePayload(page);

    await page.goto(targetUrl, { waitUntil: 'load', timeout: 120000 });
    await page.waitForLoadState('networkidle');

    if (!isExternalTarget) {
      await page.click('#heavy-action');
      await page.waitForSelector('#result span', { timeout: 10000 });
    }

    const report = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0] || {};
      const paintEntries = performance.getEntriesByType('paint');
      const firstPaint = paintEntries.find((entry) => entry.name === 'first-paint')?.startTime || 0;
      const firstContentfulPaint = paintEntries.find((entry) => entry.name === 'first-contentful-paint')?.startTime || 0;
      const lcpEntry = performance.getEntriesByType('largest-contentful-paint')[0] || {};
      const clsEntries = performance.getEntriesByType('layout-shift');
      const cls = clsEntries.reduce((sum, entry) => sum + (entry.hadRecentInput ? 0 : entry.value), 0);

      return {
        ttfb: Math.max(0, (navigation.responseStart || 0) - (navigation.requestStart || 0)),
        fcp: firstContentfulPaint,
        firstPaint,
        lcp: lcpEntry.renderTime || lcpEntry.loadTime || 0,
        cls,
        inp: window.__perf?.inp || 0,
        domContentLoaded: navigation.domContentLoadedEventEnd || 0,
        load: navigation.loadEventEnd || 0,
        interactionDelay: window.__perf?.interactionDelay || 0
      };
    });

    report.inp = report.inp || report.interactionDelay;
    report.payloadMb = getPayloadSize() / 1024 / 1024;
    report.pageUrl = page.url();
    report.budgets = PERFORMANCE_BUDGETS;
    report.targetUrl = targetUrl;
    writeReport(report);

    console.log('Performance metrics:', report);

    expect(report.ttfb).toBeLessThanOrEqual(PERFORMANCE_BUDGETS.ttfb);
    expect(report.fcp).toBeLessThanOrEqual(PERFORMANCE_BUDGETS.fcp);
    expect(report.lcp).toBeLessThanOrEqual(PERFORMANCE_BUDGETS.lcp);
    expect(report.cls).toBeLessThanOrEqual(PERFORMANCE_BUDGETS.cls);
    expect(report.inp).toBeLessThanOrEqual(PERFORMANCE_BUDGETS.inp);
    expect(report.payloadMb).toBeLessThanOrEqual(PERFORMANCE_BUDGETS.payloadMb);
  });
});
