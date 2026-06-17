# ghcp

## Accessibility audit

Run the WCAG accessibility audit using Playwright:

```bash
npm run test:a11y
```

use skill `web-accessibility\SKILL.md`

The audit saves axe output to `test-results/accessibility-results.json`.

To allow non-blocking runs for severe issues, set:

```bash
A11Y_STRICT=false npm run test:a11y
```