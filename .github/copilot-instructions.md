# GitHub Copilot Instructions for ghcp

This repository is a small static web project with Playwright-powered audits. There is no backend application code; development work focuses on the HTML page, test harness, and automation around web performance and accessibility.

## Key commands
- `npm install` — install dependencies
- `npm test` — run all Playwright tests
- `npm run test:a11y` — run the accessibility audit
- `npm run test:performance` — run the performance audit

## Important files
- `index.html` — main page under test
- `package.json` — node scripts and dev dependencies
- `playwright.config.js` — Playwright configuration, including headless Chromium and local web server
- `tests/accessibility.spec.js` — accessibility audit tests
- `tests/performance.spec.js` — performance audit tests
- `test-results/accessibility-results.json` — accessibility output artifact
- `.github/skills/wcag-accessibility/SKILL.md` — accessibility guidance for the agent
- `.github/skills/performance-test/SKILL.md` — performance guidance for the agent

## Repository conventions
- Use Playwright and `@playwright/test` for automation.
- The local server is launched on port `3000` using `python3 -m http.server 3000`.
- Tests should use `baseURL` from `playwright.config.js` and target pages under `/index.html`.
- Accessibility failures should be treated as CI blockers for `critical` or `serious` violations by default.
- When `A11Y_STRICT=false` is set, accessibility budget failures should emit warnings instead of failing the run.

## Agent behavior
- Prefer small, targeted changes over large refactors.
- Do not invent backend APIs or services; there is no backend code in this repo.
- Keep automation and test changes aligned with existing Playwright patterns.
- If introducing new scripts or artifacts, update `package.json` and `README.md` accordingly.
- Link to the existing `.github/skills` documentation when explaining accessibility or performance-specific behavior.

## Notes
- This repo is best served by maintaining the current Playwright-based QA workflow.
- Use the skill docs in `.github/skills/` as source of truth for accessibility and performance audits.
