const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const outputFile = path.join(__dirname, '..', 'test-results', 'accessibility-results.json');

function writeResults(results) {
  const dir = path.dirname(outputFile);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(outputFile, JSON.stringify(results, null, 2));
}

function reportViolations(results) {
  const severe = results.violations.filter(v => ['critical', 'serious'].includes(v.impact));
  if (results.violations.length > 0) {
    console.log('Accessibility violations:', results.violations.length);
  }

  if (severe.length > 0) {
    const message = `Severe accessibility violations found: ${severe.map(s => `${s.id} (${s.impact})`).join(', ')}`;
    if (process.env.A11Y_STRICT === 'false') {
      console.warn(message);
    } else {
      throw new Error(message);
    }
  }

  return severe;
}

test.describe('WCAG Accessibility Audit', () => {
  test('runs axe-core and fails on critical/serious violations', async ({ page }) => {
    await page.goto('/index.html', { waitUntil: 'load' });
    await page.addScriptTag({ url: 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.8.3/axe.min.js' });

    const results = await page.evaluate(async () => {
      // eslint-disable-next-line no-undef
      return await axe.run(document, {
        runOnly: {
          type: 'tag',
          values: ['wcag2a', 'wcag2aa', 'best-practice']
        }
      });
    });

    writeResults(results);
    reportViolations(results);

    expect(Array.isArray(results.violations)).toBeTruthy();
  });

  test('verifies keyboard focus traversal on the homepage', async ({ page }) => {
    await page.goto('/index.html', { waitUntil: 'load' });
    const focusOrder = [];

    for (let i = 0; i < 20; i++) {
      await page.keyboard.press('Tab');
      focusOrder.push(await page.evaluate(() => {
        const active = document.activeElement;
        if (!active) return 'none';
        return `${active.tagName.toLowerCase()}${active.id ? `#${active.id}` : ''}${active.className ? `.${active.className.toString().trim().replace(/\s+/g, '.')}` : ''}`;
      }));
    }

    console.log('Focus order sample:', focusOrder.filter(value => value !== 'none').slice(0, 10));
    expect(focusOrder.some(value => value !== 'none')).toBeTruthy();
  });
});
