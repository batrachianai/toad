/**
 * Accessibility Audit Test Template
 *
 * Comprehensive accessibility testing including:
 * - WCAG 2.1 AA automated checks (via axe-core)
 * - Keyboard navigation testing
 * - Screen reader accessibility
 * - Color contrast validation
 * - Focus management
 *
 * Usage:
 *   npm install @axe-core/playwright
 *   npx playwright test accessibility-audit.spec.ts
 */

import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// ============================================================================
// CONFIGURATION
// ============================================================================

const AUDIT_CONFIG = {
  baseUrl: 'http://localhost:3000',

  // Pages to audit
  pages: [
    { name: 'Home', path: '/' },
    { name: 'Signup', path: '/signup' },
    { name: 'Login', path: '/login' },
    { name: 'Dashboard', path: '/dashboard' },
  ],

  // WCAG conformance level
  wcagLevel: 'wcag2aa' as const,

  // Critical rules that should never fail
  criticalRules: [
    'color-contrast',
    'image-alt',
    'label',
    'link-name',
    'button-name',
  ],

  // Minimum touch target size (pixels)
  minTouchTarget: 44,
};

// ============================================================================
// TYPES
// ============================================================================

interface AccessibilityIssue {
  rule: string;
  impact: 'critical' | 'serious' | 'moderate' | 'minor';
  description: string;
  elements: string[];
  wcag: string[];
}

interface KeyboardTestResult {
  element: string;
  focusable: boolean;
  hasVisibleFocus: boolean;
  keyboardAccessible: boolean;
}

// ============================================================================
// TEST IMPLEMENTATION
// ============================================================================

test.describe('Accessibility Audit', () => {

  // Run axe-core on all configured pages
  for (const pageConfig of AUDIT_CONFIG.pages) {
    test(`WCAG ${AUDIT_CONFIG.wcagLevel} compliance: ${pageConfig.name}`, async ({ page }) => {
      await page.goto(`${AUDIT_CONFIG.baseUrl}${pageConfig.path}`);
      await page.waitForLoadState('networkidle');

      const accessibilityScanResults = await new AxeBuilder({ page })
        .withTags([AUDIT_CONFIG.wcagLevel])
        .analyze();

      // Categorize violations by impact
      const critical = accessibilityScanResults.violations.filter(v => v.impact === 'critical');
      const serious = accessibilityScanResults.violations.filter(v => v.impact === 'serious');
      const moderate = accessibilityScanResults.violations.filter(v => v.impact === 'moderate');
      const minor = accessibilityScanResults.violations.filter(v => v.impact === 'minor');

      // Report
      console.log('\n' + '═'.repeat(60));
      console.log(`♿ ACCESSIBILITY REPORT: ${pageConfig.name}`);
      console.log(`   URL: ${AUDIT_CONFIG.baseUrl}${pageConfig.path}`);
      console.log('═'.repeat(60));

      if (accessibilityScanResults.violations.length === 0) {
        console.log('✅ No accessibility violations found!');
      } else {
        console.log(`Found ${accessibilityScanResults.violations.length} violations:\n`);

        if (critical.length > 0) {
          console.log(`🔴 CRITICAL (${critical.length}):`);
          critical.forEach(v => {
            console.log(`   ${v.id}: ${v.description}`);
            console.log(`      Impact: ${v.impact} | WCAG: ${v.tags.filter(t => t.startsWith('wcag')).join(', ')}`);
            console.log(`      Elements: ${v.nodes.length} affected`);
            v.nodes.slice(0, 3).forEach(n => console.log(`        - ${n.target.join(' > ')}`));
          });
        }

        if (serious.length > 0) {
          console.log(`\n🟠 SERIOUS (${serious.length}):`);
          serious.forEach(v => {
            console.log(`   ${v.id}: ${v.description}`);
            console.log(`      Elements: ${v.nodes.length} affected`);
          });
        }

        if (moderate.length > 0) {
          console.log(`\n🟡 MODERATE (${moderate.length}):`);
          moderate.forEach(v => {
            console.log(`   ${v.id}: ${v.description}`);
          });
        }

        if (minor.length > 0) {
          console.log(`\n🟢 MINOR (${minor.length}):`);
          minor.forEach(v => {
            console.log(`   ${v.id}`);
          });
        }
      }

      // Passes
      console.log(`\n✅ Passing rules: ${accessibilityScanResults.passes.length}`);

      console.log('═'.repeat(60));

      // Critical rules should pass
      const criticalViolations = accessibilityScanResults.violations.filter(
        v => AUDIT_CONFIG.criticalRules.includes(v.id)
      );

      expect(criticalViolations, `Critical accessibility violations found`).toHaveLength(0);
    });
  }

  test('Keyboard navigation works throughout the application', async ({ page }) => {
    await page.goto(AUDIT_CONFIG.baseUrl);
    await page.waitForLoadState('networkidle');

    const results: KeyboardTestResult[] = [];

    // Get all interactive elements
    const interactiveElements = await page.locator(
      'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"]), [role="button"], [role="link"]'
    ).all();

    console.log('\n' + '═'.repeat(60));
    console.log('⌨️  KEYBOARD NAVIGATION TEST');
    console.log('═'.repeat(60));
    console.log(`Testing ${interactiveElements.length} interactive elements\n`);

    // Tab through all elements
    let tabCount = 0;
    const maxTabs = 100; // Prevent infinite loops
    const focusedElements: string[] = [];

    // Start from body
    await page.keyboard.press('Tab');
    tabCount++;

    while (tabCount < maxTabs) {
      const focusedElement = await page.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) return null;
        return {
          tag: el.tagName.toLowerCase(),
          id: el.id,
          className: el.className,
          text: el.textContent?.slice(0, 30),
          hasVisibleFocus: window.getComputedStyle(el).outlineStyle !== 'none' ||
                          window.getComputedStyle(el).boxShadow !== 'none',
        };
      });

      if (!focusedElement) break;

      const elementId = focusedElement.id || focusedElement.text || focusedElement.className;
      focusedElements.push(`${focusedElement.tag}${elementId ? `: ${elementId.slice(0, 20)}` : ''}`);

      results.push({
        element: `${focusedElement.tag}#${focusedElement.id || 'no-id'}`,
        focusable: true,
        hasVisibleFocus: focusedElement.hasVisibleFocus,
        keyboardAccessible: true,
      });

      await page.keyboard.press('Tab');
      tabCount++;

      // Check if we've looped back
      const newFocused = await page.evaluate(() => document.activeElement?.tagName);
      if (tabCount > 3 && newFocused === 'BODY') break;
    }

    // Report focus order
    console.log('Tab Order:');
    focusedElements.forEach((el, i) => console.log(`  ${i + 1}. ${el}`));

    // Check for visible focus indicators
    const withoutVisibleFocus = results.filter(r => !r.hasVisibleFocus);
    if (withoutVisibleFocus.length > 0) {
      console.log(`\n⚠️  Elements without visible focus indicator: ${withoutVisibleFocus.length}`);
      withoutVisibleFocus.forEach(r => console.log(`   - ${r.element}`));
    } else {
      console.log('\n✅ All focused elements have visible focus indicators');
    }

    console.log('═'.repeat(60));

    expect(withoutVisibleFocus.length).toBe(0);
  });

  test('Touch targets meet minimum size requirements', async ({ page }) => {
    await page.goto(AUDIT_CONFIG.baseUrl);
    await page.waitForLoadState('networkidle');

    const interactiveElements = await page.locator(
      'a, button, input, select, textarea, [role="button"], [role="link"], [onclick]'
    ).all();

    console.log('\n' + '═'.repeat(60));
    console.log('👆 TOUCH TARGET SIZE TEST');
    console.log(`   Minimum required: ${AUDIT_CONFIG.minTouchTarget}×${AUDIT_CONFIG.minTouchTarget}px`);
    console.log('═'.repeat(60));

    const undersizedTargets: { element: string; size: string }[] = [];

    for (const element of interactiveElements) {
      const box = await element.boundingBox();
      if (box) {
        if (box.width < AUDIT_CONFIG.minTouchTarget || box.height < AUDIT_CONFIG.minTouchTarget) {
          const text = await element.textContent();
          undersizedTargets.push({
            element: `${await element.evaluate(el => el.tagName.toLowerCase())}${text ? `: "${text.slice(0, 20)}"` : ''}`,
            size: `${Math.round(box.width)}×${Math.round(box.height)}px`,
          });
        }
      }
    }

    if (undersizedTargets.length > 0) {
      console.log(`\n⚠️  Undersized touch targets: ${undersizedTargets.length}`);
      undersizedTargets.forEach(t => console.log(`   - ${t.element} (${t.size})`));
    } else {
      console.log('\n✅ All touch targets meet minimum size requirements');
    }

    console.log('═'.repeat(60));

    // Warning, not failure (some small elements may be intentional)
    if (undersizedTargets.length > 5) {
      console.warn('Too many undersized touch targets - review for mobile usability');
    }
  });

  test('Forms have proper labeling', async ({ page }) => {
    await page.goto(AUDIT_CONFIG.baseUrl);
    await page.waitForLoadState('networkidle');

    console.log('\n' + '═'.repeat(60));
    console.log('📝 FORM ACCESSIBILITY TEST');
    console.log('═'.repeat(60));

    const inputs = await page.locator('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea').all();
    const issues: string[] = [];

    for (const input of inputs) {
      const id = await input.getAttribute('id');
      const name = await input.getAttribute('name');
      const type = await input.getAttribute('type') || 'text';
      const ariaLabel = await input.getAttribute('aria-label');
      const ariaLabelledBy = await input.getAttribute('aria-labelledby');
      const placeholder = await input.getAttribute('placeholder');

      // Check for associated label
      let hasLabel = false;
      if (id) {
        const label = await page.locator(`label[for="${id}"]`).count();
        hasLabel = label > 0;
      }

      const hasAriaLabel = !!ariaLabel || !!ariaLabelledBy;

      if (!hasLabel && !hasAriaLabel) {
        issues.push(`Input [type="${type}"] name="${name || 'unnamed'}" has no label or aria-label`);

        if (placeholder) {
          issues.push(`  ⚠️  Uses placeholder "${placeholder}" as label (not accessible)`);
        }
      }
    }

    if (issues.length > 0) {
      console.log(`\n❌ Form labeling issues: ${issues.length}`);
      issues.forEach(i => console.log(`   ${i}`));
    } else {
      console.log('\n✅ All form inputs have proper labels');
    }

    console.log('═'.repeat(60));

    expect(issues.length).toBe(0);
  });

  test('Images have alt text', async ({ page }) => {
    await page.goto(AUDIT_CONFIG.baseUrl);
    await page.waitForLoadState('networkidle');

    console.log('\n' + '═'.repeat(60));
    console.log('🖼️  IMAGE ACCESSIBILITY TEST');
    console.log('═'.repeat(60));

    const images = await page.locator('img').all();
    const missingAlt: string[] = [];
    const emptyAlt: string[] = [];

    for (const img of images) {
      const alt = await img.getAttribute('alt');
      const src = await img.getAttribute('src');
      const role = await img.getAttribute('role');

      // Decorative images can have empty alt or role="presentation"
      if (role === 'presentation' || role === 'none') continue;

      if (alt === null) {
        missingAlt.push(src || 'unknown source');
      } else if (alt === '' && role !== 'presentation') {
        // Empty alt should only be used for decorative images
        emptyAlt.push(src || 'unknown source');
      }
    }

    console.log(`Total images: ${images.length}`);

    if (missingAlt.length > 0) {
      console.log(`\n❌ Images missing alt attribute: ${missingAlt.length}`);
      missingAlt.slice(0, 5).forEach(src => console.log(`   - ${src.slice(0, 50)}`));
    }

    if (emptyAlt.length > 0) {
      console.log(`\n⚠️  Images with empty alt (verify decorative): ${emptyAlt.length}`);
    }

    if (missingAlt.length === 0) {
      console.log('\n✅ All images have alt attributes');
    }

    console.log('═'.repeat(60));

    expect(missingAlt.length).toBe(0);
  });

  test('Color contrast meets WCAG AA standards', async ({ page }) => {
    await page.goto(AUDIT_CONFIG.baseUrl);
    await page.waitForLoadState('networkidle');

    // Use axe-core specifically for color contrast
    const results = await new AxeBuilder({ page })
      .withRules(['color-contrast'])
      .analyze();

    console.log('\n' + '═'.repeat(60));
    console.log('🎨 COLOR CONTRAST TEST');
    console.log('═'.repeat(60));

    if (results.violations.length === 0) {
      console.log('✅ All text meets WCAG AA contrast requirements');
    } else {
      console.log(`\n❌ Contrast violations: ${results.violations[0]?.nodes.length || 0} elements`);
      results.violations[0]?.nodes.slice(0, 5).forEach(node => {
        console.log(`   - ${node.target.join(' > ')}`);
        console.log(`     ${node.failureSummary}`);
      });
    }

    console.log('═'.repeat(60));

    expect(results.violations).toHaveLength(0);
  });
});

// ============================================================================
// FULL PAGE AUDIT SUMMARY
// ============================================================================

test('Generate full accessibility audit summary', async ({ page }) => {
  console.log('\n' + '╔'.padEnd(59, '═') + '╗');
  console.log('║' + '  FULL ACCESSIBILITY AUDIT SUMMARY'.padEnd(58) + '║');
  console.log('╚'.padEnd(59, '═') + '╝');

  const pageResults: { page: string; violations: number; critical: number }[] = [];

  for (const pageConfig of AUDIT_CONFIG.pages) {
    try {
      await page.goto(`${AUDIT_CONFIG.baseUrl}${pageConfig.path}`, { timeout: 10000 });
      await page.waitForLoadState('networkidle');

      const results = await new AxeBuilder({ page })
        .withTags([AUDIT_CONFIG.wcagLevel])
        .analyze();

      const critical = results.violations.filter(v => v.impact === 'critical' || v.impact === 'serious').length;

      pageResults.push({
        page: pageConfig.name,
        violations: results.violations.length,
        critical,
      });
    } catch (e) {
      pageResults.push({
        page: pageConfig.name,
        violations: -1,
        critical: -1,
      });
    }
  }

  console.log('\n┌──────────────────────┬────────────┬──────────┐');
  console.log('│ Page                 │ Violations │ Critical │');
  console.log('├──────────────────────┼────────────┼──────────┤');

  pageResults.forEach(r => {
    const status = r.violations === -1 ? 'Error' : r.critical === 0 ? '✅' : '❌';
    console.log(`│ ${r.page.padEnd(20)} │ ${String(r.violations).padStart(10)} │ ${String(r.critical).padStart(6)} ${status} │`);
  });

  console.log('└──────────────────────┴────────────┴──────────┘');

  const totalCritical = pageResults.reduce((sum, r) => sum + (r.critical > 0 ? r.critical : 0), 0);

  console.log(`\nTotal critical issues: ${totalCritical}`);
  console.log(totalCritical === 0 ? '✅ PASSED' : '❌ NEEDS ATTENTION');
});
