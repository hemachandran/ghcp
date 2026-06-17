# Accessibility Audit Report: http://agentskills.io/home

Generated: 2026-06-17T16:23:06.221Z

## Summary
- URL: https://agentskills.io/home
- Engine: axe-core 4.8.3
- Violations: 4
- serious: 3
- moderate: 1

## Violations
### 1. ARIA commands must have an accessible name
- id: aria-command-name
- impact: serious
- description: Ensures every ARIA button, link and menuitem has an accessible name
- helpUrl: https://dequeuniversity.com/rules/axe/4.8/aria-command-name?application=axeAPI
- nodes: 2
  - node 1: <div class="card block font-normal group relative my-2 ring-2 ring-transparent rounded-2xl bg-white dark:bg-background-dark border border-gray-950/10 dark:border-white/10 overflow-hidden w-full cursor-pointer hover:!border-primary dark:hover:!border-primary-light" tabindex="0" role="link">
    - failureSummary: Fix any of the following: Element does not have text that is visible to screen readers aria-label attribute does not exist or is empty aria-labelledby attribute does not exist, references elements that do not exist or references elements that are empty Element has no title attribute
  - node 2: <div class="card block font-normal group relative my-2 ring-2 ring-transparent rounded-2xl bg-white dark:bg-background-dark border border-gray-950/10 dark:border-white/10 overflow-hidden w-full cursor-pointer hover:!border-primary dark:hover:!border-primary-light" tabindex="0" role="link">
    - failureSummary: Fix any of the following: Element does not have text that is visible to screen readers aria-label attribute does not exist or is empty aria-labelledby attribute does not exist, references elements that do not exist or references elements that are empty Element has no title attribute

### 2. ARIA hidden element must not be focusable or contain focusable elements
- id: aria-hidden-focus
- impact: serious
- description: Ensures aria-hidden elements are not focusable nor contain focusable elements
- helpUrl: https://dequeuniversity.com/rules/axe/4.8/aria-hidden-focus?application=axeAPI
- nodes: 1
  - node 1: <blockquote class="sr-only" data-agent-docs-index="true" aria-hidden="true"><h2>Documentation Index</h2><p>Fetch the complete documentation index at: <a href="/llms.txt">/llms.txt</a></p><p>Use this file to discover all available pages before exploring further.</p></blockquote>
    - failureSummary: Fix all of the following: Focusable content should have tabindex="-1" or be removed from the DOM

### 3. Elements must meet minimum color contrast ratio thresholds
- id: color-contrast
- impact: serious
- description: Ensures the contrast between foreground and background colors meets WCAG 2 AA minimum contrast ratio thresholds
- helpUrl: https://dequeuniversity.com/rules/axe/4.8/color-contrast?application=axeAPI
- nodes: 2
  - node 1: <span class="min-w-0 max-w-full break-words hyphens-auto">Overview</span>
    - failureSummary: Fix any of the following: Element has insufficient color contrast of 3.57 (foreground color: #7f7f7f, background color: #f2f2f2, font size: 10.5pt (14px), font weight: normal). Expected contrast ratio of 4.5:1
  - node 2: <a href="#what-are-agent-skills" class="break-words py-1 block text-primary dark:text-primary-light [text-shadow:-0.15px_0_0_currentColor,0.15px_0_0_currentColor] border-primary dark:border-primary-light hover:border-primary dark:hover:border-primary-light" aria-current="location">
    - failureSummary: Fix any of the following: Element has insufficient color contrast of 4 (foreground color: #7f7f7f, background color: #ffffff, font size: 10.5pt (14px), font weight: normal). Expected contrast ratio of 4.5:1

### 4. All page content should be contained by landmarks
- id: region
- impact: moderate
- description: Ensures all page content is contained by landmarks
- helpUrl: https://dequeuniversity.com/rules/axe/4.8/region?application=axeAPI
- nodes: 1
  - node 1: <a href="#content-area" class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:p-2 focus:text-sm focus:bg-background-light dark:focus:bg-background-dark focus:rounded-md focus:outline-primary dark:focus:outline-primary-light">Skip to main content</a>
    - failureSummary: Fix any of the following: Some page content is not contained by landmarks
