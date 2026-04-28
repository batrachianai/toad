/**
 * Synthetic User Testing Template
 *
 * Simulates different user personas interacting with your product.
 * Each persona has distinct behaviors, patience levels, and patterns.
 *
 * Usage:
 *   npx playwright test synthetic-user-test.spec.ts
 */

import { test, expect, type Page } from '@playwright/test';

// ============================================================================
// PERSONA DEFINITIONS
// ============================================================================

interface UserPersona {
  name: string;
  shortName: string;
  description: string;
  behaviors: {
    readsInstructions: boolean;
    patience: 'low' | 'medium' | 'high';
    clickSpeed: 'fast' | 'normal' | 'slow';
    scrollBehavior: 'skims' | 'reads' | 'thorough';
    errorTolerance: number; // 0-3 errors before abandoning
    usesKeyboard: boolean;
  };
  expectations: {
    maxTimeToFirstAction: number; // ms
    maxClicksToComplete: number;
    expectsProgressIndicator: boolean;
    needsHelpText: boolean;
  };
}

const PERSONAS: UserPersona[] = [
  {
    name: 'Impatient Power User',
    shortName: 'Alex',
    description: 'Expert user who expects efficiency and shortcuts',
    behaviors: {
      readsInstructions: false,
      patience: 'low',
      clickSpeed: 'fast',
      scrollBehavior: 'skims',
      errorTolerance: 1,
      usesKeyboard: true,
    },
    expectations: {
      maxTimeToFirstAction: 2000,
      maxClicksToComplete: 5,
      expectsProgressIndicator: false,
      needsHelpText: false,
    },
  },
  {
    name: 'Confused First-Timer',
    shortName: 'Jordan',
    description: 'New user who needs guidance at every step',
    behaviors: {
      readsInstructions: true,
      patience: 'medium',
      clickSpeed: 'slow',
      scrollBehavior: 'thorough',
      errorTolerance: 2,
      usesKeyboard: false,
    },
    expectations: {
      maxTimeToFirstAction: 10000,
      maxClicksToComplete: 15,
      expectsProgressIndicator: true,
      needsHelpText: true,
    },
  },
  {
    name: 'Accessibility-Dependent User',
    shortName: 'Sam',
    description: 'Uses keyboard-only navigation and screen reader',
    behaviors: {
      readsInstructions: true,
      patience: 'high',
      clickSpeed: 'normal',
      scrollBehavior: 'reads',
      errorTolerance: 2,
      usesKeyboard: true,
    },
    expectations: {
      maxTimeToFirstAction: 15000,
      maxClicksToComplete: 20,
      expectsProgressIndicator: true,
      needsHelpText: true,
    },
  },
  {
    name: 'Skeptical Evaluator',
    shortName: 'Riley',
    description: 'Evaluating product, looking for problems',
    behaviors: {
      readsInstructions: true,
      patience: 'medium',
      clickSpeed: 'normal',
      scrollBehavior: 'thorough',
      errorTolerance: 0,
      usesKeyboard: false,
    },
    expectations: {
      maxTimeToFirstAction: 5000,
      maxClicksToComplete: 10,
      expectsProgressIndicator: true,
      needsHelpText: false,
    },
  },
  {
    name: 'Distracted Mobile User',
    shortName: 'Casey',
    description: 'On phone, frequently interrupted, limited attention',
    behaviors: {
      readsInstructions: false,
      patience: 'low',
      clickSpeed: 'fast',
      scrollBehavior: 'skims',
      errorTolerance: 1,
      usesKeyboard: false,
    },
    expectations: {
      maxTimeToFirstAction: 3000,
      maxClicksToComplete: 8,
      expectsProgressIndicator: true,
      needsHelpText: false,
    },
  },
];

// ============================================================================
// CONFIGURATION
// ============================================================================

const TEST_CONFIG = {
  baseUrl: 'http://localhost:3000',
  task: 'Complete signup flow',
  successSelector: '[data-testid="signup-success"], [data-testid="dashboard"]',
};

// ============================================================================
// TEST IMPLEMENTATION
// ============================================================================

interface PersonaTestResult {
  persona: string;
  completed: boolean;
  timeSpent: number;
  clicks: number;
  errorsEncountered: number;
  abandonmentReason?: string;
  frustrationPoints: string[];
  positivePoints: string[];
}

async function simulatePersonaBehavior(
  page: Page,
  persona: UserPersona
): Promise<PersonaTestResult> {
  const result: PersonaTestResult = {
    persona: persona.name,
    completed: false,
    timeSpent: 0,
    clicks: 0,
    errorsEncountered: 0,
    frustrationPoints: [],
    positivePoints: [],
  };

  const startTime = Date.now();

  // ========================================================================
  // STEP 1: Initial Page Load Evaluation
  // ========================================================================

  // Check time to interactive
  const loadTime = Date.now() - startTime;
  if (loadTime > persona.expectations.maxTimeToFirstAction) {
    result.frustrationPoints.push(
      `Page load too slow for ${persona.shortName} (${loadTime}ms > ${persona.expectations.maxTimeToFirstAction}ms)`
    );

    if (persona.behaviors.patience === 'low') {
      result.abandonmentReason = 'Page load too slow';
      result.timeSpent = loadTime;
      return result;
    }
  }

  // Check for clear call-to-action
  const primaryCTA = page.locator('button, a[href]').filter({
    hasText: /start|sign up|get started|begin|create/i
  }).first();

  const ctaVisible = await primaryCTA.isVisible().catch(() => false);

  if (!ctaVisible) {
    result.frustrationPoints.push(`No clear CTA visible for ${persona.shortName}`);

    if (!persona.behaviors.readsInstructions) {
      result.abandonmentReason = 'Could not find how to start';
      result.timeSpent = Date.now() - startTime;
      return result;
    }
  } else {
    result.positivePoints.push('Clear CTA immediately visible');
  }

  // ========================================================================
  // STEP 2: Keyboard Navigation Check (for keyboard users)
  // ========================================================================

  if (persona.behaviors.usesKeyboard) {
    // Try to Tab to the CTA
    let tabCount = 0;
    const maxTabs = 20;
    let reachedCTA = false;

    await page.keyboard.press('Tab');
    tabCount++;

    while (tabCount < maxTabs) {
      const focused = await page.evaluate(() => document.activeElement?.textContent);
      if (focused?.match(/start|sign up|get started|begin|create/i)) {
        reachedCTA = true;
        break;
      }
      await page.keyboard.press('Tab');
      tabCount++;
    }

    if (!reachedCTA) {
      result.frustrationPoints.push(
        `${persona.shortName} couldn't reach CTA via keyboard (${tabCount} tabs)`
      );
    } else {
      result.positivePoints.push(`CTA reachable in ${tabCount} tabs`);
    }

    // Check focus visibility
    const hasFocusStyle = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el) return false;
      const style = window.getComputedStyle(el);
      return style.outlineStyle !== 'none' || style.boxShadow !== 'none';
    });

    if (!hasFocusStyle) {
      result.frustrationPoints.push('No visible focus indicator');
    }
  }

  // ========================================================================
  // STEP 3: Progress Indicator Check
  // ========================================================================

  if (persona.expectations.expectsProgressIndicator) {
    const hasProgress = await page.locator(
      '[role="progressbar"], .progress, .steps, [data-step], .stepper'
    ).count() > 0;

    if (!hasProgress) {
      result.frustrationPoints.push(
        `${persona.shortName} expects progress indicator but none found`
      );
    }
  }

  // ========================================================================
  // STEP 4: Help Text Check
  // ========================================================================

  if (persona.expectations.needsHelpText) {
    const hasHelp = await page.locator(
      '[aria-describedby], .help-text, .hint, [data-tooltip], .tooltip'
    ).count() > 0;

    if (!hasHelp) {
      result.frustrationPoints.push(
        `${persona.shortName} needs help text but none found`
      );
    }
  }

  // ========================================================================
  // STEP 5: Attempt to Complete Task
  // ========================================================================

  // Click CTA
  if (ctaVisible) {
    result.clicks++;
    await primaryCTA.click();

    // Wait for navigation/response
    await page.waitForTimeout(persona.behaviors.clickSpeed === 'fast' ? 500 : 1500);
  }

  // Look for form
  const formInputs = page.locator('input:visible, select:visible, textarea:visible');
  const inputCount = await formInputs.count();

  if (inputCount > 0) {
    // Check form field count
    if (inputCount > 5 && persona.behaviors.patience === 'low') {
      result.frustrationPoints.push(
        `Too many form fields (${inputCount}) for ${persona.shortName}`
      );
    }

    // Check for placeholder-only labels (accessibility issue)
    const inputs = await formInputs.all();
    for (const input of inputs) {
      const hasLabel = await page.locator(`label[for="${await input.getAttribute('id')}"]`).count() > 0;
      const hasAriaLabel = await input.getAttribute('aria-label');

      if (!hasLabel && !hasAriaLabel) {
        result.frustrationPoints.push('Form field missing label');
        result.errorsEncountered++;

        if (result.errorsEncountered > persona.behaviors.errorTolerance) {
          result.abandonmentReason = 'Too many accessibility issues';
          result.timeSpent = Date.now() - startTime;
          return result;
        }
      }
    }

    // Fill form fields (simplified)
    const emailInput = page.locator('[type="email"], [name="email"]').first();
    if (await emailInput.isVisible()) {
      result.clicks++;
      await emailInput.fill('test@example.com');
    }

    const passwordInput = page.locator('[type="password"]').first();
    if (await passwordInput.isVisible()) {
      result.clicks++;
      await passwordInput.fill('TestPassword123!');
    }
  }

  // Try to submit
  const submitButton = page.locator('[type="submit"], button:has-text("Submit"), button:has-text("Continue")').first();
  if (await submitButton.isVisible()) {
    result.clicks++;
    await submitButton.click();

    // Wait for result
    await page.waitForTimeout(2000);

    // Check for success
    const success = await page.locator(TEST_CONFIG.successSelector).isVisible().catch(() => false);
    result.completed = success;

    // Check for error
    const errorVisible = await page.locator('[role="alert"], .error, [data-error]').isVisible().catch(() => false);
    if (errorVisible) {
      result.errorsEncountered++;
      result.frustrationPoints.push('Encountered error during submission');
    }
  }

  // ========================================================================
  // STEP 6: Final Evaluation
  // ========================================================================

  result.timeSpent = Date.now() - startTime;

  // Check if clicks exceeded expectation
  if (result.clicks > persona.expectations.maxClicksToComplete) {
    result.frustrationPoints.push(
      `Too many clicks required (${result.clicks} > ${persona.expectations.maxClicksToComplete})`
    );
  } else {
    result.positivePoints.push(`Completed in ${result.clicks} clicks`);
  }

  return result;
}

// ============================================================================
// TESTS
// ============================================================================

test.describe('Synthetic User Testing', () => {
  for (const persona of PERSONAS) {
    test(`${persona.name} (${persona.shortName}) attempts task`, async ({ page }) => {
      // Set viewport based on persona
      if (persona.shortName === 'Casey') {
        await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE
      }

      await page.goto(TEST_CONFIG.baseUrl);
      await page.waitForLoadState('networkidle');

      const result = await simulatePersonaBehavior(page, persona);

      // Generate report
      console.log('\n' + '═'.repeat(60));
      console.log(`👤 SYNTHETIC USER TEST: ${persona.name}`);
      console.log(`   "${persona.description}"`);
      console.log('═'.repeat(60));
      console.log(`\nTask: ${TEST_CONFIG.task}`);
      console.log(`Result: ${result.completed ? '✅ COMPLETED' : '❌ ' + (result.abandonmentReason || 'FAILED')}`);
      console.log(`Time: ${result.timeSpent}ms`);
      console.log(`Clicks: ${result.clicks}`);
      console.log(`Errors: ${result.errorsEncountered}`);

      if (result.frustrationPoints.length > 0) {
        console.log('\n😤 Frustration Points:');
        result.frustrationPoints.forEach(p => console.log(`   - ${p}`));
      }

      if (result.positivePoints.length > 0) {
        console.log('\n😊 Positive Points:');
        result.positivePoints.forEach(p => console.log(`   - ${p}`));
      }

      console.log('═'.repeat(60));

      // Soft assertions (don't fail test, but report)
      if (!result.completed) {
        console.warn(`⚠️ ${persona.shortName} could not complete task: ${result.abandonmentReason}`);
      }
    });
  }

  test('Generate persona comparison summary', async ({ page }) => {
    console.log('\n' + '╔'.padEnd(79, '═') + '╗');
    console.log('║' + '  PERSONA COMPARISON SUMMARY'.padEnd(78) + '║');
    console.log('╚'.padEnd(79, '═') + '╝');

    console.log('\n┌─────────────────────────┬───────────┬─────────┬────────┬─────────────────┐');
    console.log('│ Persona                 │ Completed │ Time    │ Clicks │ Frustrations    │');
    console.log('├─────────────────────────┼───────────┼─────────┼────────┼─────────────────┤');

    for (const persona of PERSONAS) {
      await page.goto(TEST_CONFIG.baseUrl);
      await page.waitForLoadState('networkidle');

      const result = await simulatePersonaBehavior(page, persona);

      const status = result.completed ? '✅' : '❌';
      const time = `${Math.round(result.timeSpent / 1000)}s`;
      const frustrations = result.frustrationPoints.length;

      console.log(
        `│ ${persona.name.padEnd(23)} │ ${status.padEnd(9)} │ ${time.padStart(7)} │ ${String(result.clicks).padStart(6)} │ ${String(frustrations).padStart(15)} │`
      );
    }

    console.log('└─────────────────────────┴───────────┴─────────┴────────┴─────────────────┘');

    console.log('\nKey:');
    console.log('  ✅ = Successfully completed task');
    console.log('  ❌ = Failed or abandoned task');
    console.log('\nPrioritize fixing issues affecting multiple personas.');
  });
});
