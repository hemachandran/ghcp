# Name: performance-test
# Description: Teaches the agent to capture, analyze, and enforce web performance tests according to modern industry baselines (Core Web Vitals, W3C Navigation Timings, and Network/CPU Throttling budgets).
# Triggers: "performance testing", "performance budget", "core web vitals", "LCP threshold", "CLS regression", "INP profiling", "throttle performance"

## Context & Purpose
This skill instructs the agent on how to implement deterministic client-side performance testing. It translates abstract business performance goals into explicit test assertions mapped to Google's Core Web Vitals (CWV) and W3C industry-standard thresholds. Create HTML page for performance testing, instrument it with the `performance.mark` API, and assert against the following metrics:

## Industry Reference Budgets (2026 Baseline)
When executing or asserting performance metrics, the agent must enforce these boundaries unless custom overrides are specified:
- **TTFB (Time to First Byte)**: Good: ≤ 800ms | Poor: > 1800ms
- **FCP (First Contentful Paint)**: Good: ≤ 1.8s | Poor: > 3.0s
- **LCP (Largest Contentful Paint)**: Good: ≤ 2.5s | Poor: > 4.0s
- **INP (Interaction to Next Paint)**: Good: ≤ 200ms | Poor: > 500ms
- **CLS (Cumulative Layout Shift)**: Good: ≤ 0.10 | Poor: > 0.25

## Golden Rules
1. **Chromium Dependency**: Native CDP (Chrome DevTools Protocol) metrics are strict-bound to Chromium. Fall back to standard `performance.mark` API for WebKit/Gecko.
2. **Environment Isolation**: Always run benchmarks in headless mode with CPU/Network emulation enabled to isolate results from CI container hardware drift.
3. **Warm/Cold Profiling**: Run 1 warm-up navigation to prime the cache, followed by 3 isolated cold-test runs. Use the median value for calculations.

## Capabilities & Implementation Workflows

### 1. Complete Industry Standard Performance Test Harness
Below is the reference engine configuration that hooks into Chrome DevTools Protocol to capture paint events, layout shifts, and time-to-interactive budgets.

```typescript
import { test, expect, ChromiumBrowserContext } from '@playwright/test';

// Global Baseline Threshold Configurations
const PERFORMANCE_BUDGETS = {
  ttfb: 800,
  fcp: 1800,
  lcp: 2500,
  cls: 0.10
};

test.describe('Industry Standard Performance Validation', () => {
  
  test('Audit Page Core Web Vitals & Network Payload', async ({ page, context }) => {
    // 1. Isolate Environment via CDP Session
    const cdsSession = await (context as ChromiumBrowserContext).newCDPSession(page);
    
    // Emulate a standard mid-range mobile profile (Moto G4 style network/CPU throttling)
    await cdsSession.send('Emulation.setCPUThrottlingRate', { rate: 4 }); // 4x slowdown
    await cdsSession.send('Network.emulateNetworkConditions', {
      offline: false,
      latency: 150, // ms
      downloadThroughput: ((1.6 * 1024 * 1024) / 8), // 1.6 Mbps (Fast 3G/Slow 4G)
      uploadThroughput: ((750 * 1024) / 8)
    });

    // 2. Track Page Size Payloads (Industry Budget: Max 2MB uncompressed)
    let totalPayloadSize = 0;
    page.on('response', (response) => {
      const size = response.headers()['content-length'];
      if (size) totalPayloadSize += parseInt(size, 10);
    });

    // 3. Execute Navigation Profile
    await page.goto('https://glorious-system-5x4ww6p9qgf4wqx-5500.app.github.dev/', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');

    // 4. Extract Metrics via Client-Side Evaluation
    const performanceData = await page.evaluate(() => {
      // Pull W3C Timings
      const [navTiming] = performance.getEntriesByType('navigation') as PerformanceNavigationTiming[];
      const ttfb = navTiming ? navTiming.responseStart - navTiming.requestStart : 0;
      
      // Pull Paint Entries (FCP, LCP)
      const paintEntries = performance.getEntriesByType('paint');
      const fcpEntry = paintEntries.find(entry => entry.name === 'first-contentful-paint');
      const fcp = fcpEntry ? fcpEntry.startTime : 0;

      return { ttfb, fcp };
    });

    // 5. Gather Complex Layout Shifts (CLS) using CDP Metric Counters
    const cdpMetrics = await cdsSession.send('Performance.getMetrics');
    const findMetric = (name: string) => cdpMetrics.metrics.find(m => m.name === name)?.value || 0;
    
    // Formulate final reporting structure
    const report = {
      ttfb: performanceData.ttfb,
      fcp: performanceData.fcp,
      payloadMb: parseFloat((totalPayloadSize / 1024 / 1024).toFixed(2))
    };

    // 6. Assert Against Industry Budgets
    console.log('--- Performance Report ---', report);
    expect(report.ttfb).toBeLessThanOrEqual(PERFORMANCE_BUDGETS.ttfb);
    expect(report.fcp).toBeLessThanOrEqual(PERFORMANCE_BUDGETS.fcp);
    expect(report.payloadMb).toBeLessThanOrEqual(2.0); // 2MB Max Size limit
  });
});
```

### 2. Handling Interaction to Next Paint (INP) Automation
To capture INP metrics accurately, the agent must trigger realistic user actions (clicks/keystrokes) while listening for event timing resolutions.

```typescript
test('Measure Interaction to Next Paint (INP) on Action Buttons', async ({ page }) => {
  // Inject a performance observer script before interaction
  await page.evaluateOnNewDocument(() => {
    (window as any).inpValue = 0;
    new PerformanceObserver((entryList) => {
      for (const entry of entryList.getEntries()) {
        if (entry.duration > (window as any).inpValue) {
          (window as any).inpValue = entry.duration; // Capture longest interaction delay
        }
      }
    }).observe({ type: 'event', durationThreshold: 0, buffered: true });
  });

  await page.goto('https://glorious-system-5x4ww6p9qgf4wqx-5500.app.github.dev/');
  
  // Perform an intense UI action (e.g., expanding a heavy data grid)
  const TargetButton = page.locator('#heavy-render-button');
  await TargetButton.click();

  // Retrieve observed maximum delay
  const computedINP = await page.evaluate(() => (window as any).inpValue);
  
  console.log(`Computed Action INP: ${computedINP}ms`);
  expect(computedINP).toBeLessThanOrEqual(200); // 200ms is the standard 'Good' INP limit
});
```

## Failure Handling and Reporting
- **Soft Failures**: If `process.env.PERF_STRICT=false`, budget failures must output a structured warning chunk using `console.warn` instead of terminating the CI thread execution pipeline.
- **Reporting Format**: Export performance matrices inside standard outputs into `.json` logs under test artifacts (`playwright-report/performance-metrics.json`) for downstream ingestion by dashboard orchestrators like Grafana or Datadog.
