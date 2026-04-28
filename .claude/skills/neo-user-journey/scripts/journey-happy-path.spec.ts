/**
 * User Journey Happy Path Test Template
 *
 * Tests the primary user flow through the application.
 * Validates that the core journey can be completed successfully.
 *
 * Usage:
 *   npx playwright test journey-happy-path.spec.ts
 *
 * Configuration:
 *   Update JOURNEY_CONFIG below to match your application.
 */

import { test, expect, type Page } from '@playwright/test';

// ============================================================================
// CONFIGURATION - Update these values for your journey
// ============================================================================

const JOURNEY_CONFIG = {
  name: 'User Signup Journey',
  baseUrl: 'http://localhost:3000',

  // Define journey steps
  steps: [
    {
      name: 'Landing Page',
      url: '/',
      waitFor: '[data-testid="hero-section"]',
      actions: [
        { type: 'click', selector: '[data-testid="cta-signup"]' }
      ],
      assertions: [
        { type: 'visible', selector: '[data-testid="hero-section"]' },
        { type: 'text', selector: 'h1', contains: 'Welcome' }
      ]
    },
    {
      name: 'Signup Form',
      url: '/signup',
      waitFor: '[data-testid="signup-form"]',
      actions: [
        { type: 'fill', selector: '[name="email"]', value: 'test@example.com' },
        { type: 'fill', selector: '[name="password"]', value: 'SecurePass123!' },
        { type: 'click', selector: '[type="submit"]' }
      ],
      assertions: [
        { type: 'visible', selector: '[data-testid="signup-form"]' }
      ]
    },
    {
      name: 'Onboarding',
      url: '/onboarding',
      waitFor: '[data-testid="onboarding-step"]',
      actions: [
        { type: 'click', selector: '[data-testid="continue-btn"]' }
      ],
      assertions: [
        { type: 'visible', selector: '[data-testid="progress-indicator"]' }
      ]
    },
    {
      name: 'Dashboard',
      url: '/dashboard',
      waitFor: '[data-testid="dashboard"]',
      actions: [],
      assertions: [
        { type: 'visible', selector: '[data-testid="dashboard"]' },
        { type: 'text', selector: '[data-testid="welcome-message"]', contains: 'Welcome' }
      ]
    }
  ]
};

// ============================================================================
// TEST IMPLEMENTATION
// ============================================================================

interface JourneyStep {
  name: string;
  url: string;
  waitFor: string;
  actions: Action[];
  assertions: Assertion[];
}

interface Action {
  type: 'click' | 'fill' | 'select' | 'check' | 'hover';
  selector: string;
  value?: string;
}

interface Assertion {
  type: 'visible' | 'hidden' | 'text' | 'url' | 'count';
  selector?: string;
  contains?: string;
  value?: string | number;
}

async function executeAction(page: Page, action: Action): Promise<void> {
  const element = page.locator(action.selector);

  switch (action.type) {
    case 'click':
      await element.click();
      break;
    case 'fill':
      await element.fill(action.value || '');
      break;
    case 'select':
      await element.selectOption(action.value || '');
      break;
    case 'check':
      await element.check();
      break;
    case 'hover':
      await element.hover();
      break;
  }
}

async function executeAssertion(page: Page, assertion: Assertion): Promise<void> {
  switch (assertion.type) {
    case 'visible':
      await expect(page.locator(assertion.selector!)).toBeVisible();
      break;
    case 'hidden':
      await expect(page.locator(assertion.selector!)).toBeHidden();
      break;
    case 'text':
      await expect(page.locator(assertion.selector!)).toContainText(assertion.contains!);
      break;
    case 'url':
      await expect(page).toHaveURL(new RegExp(assertion.contains!));
      break;
    case 'count':
      await expect(page.locator(assertion.selector!)).toHaveCount(assertion.value as number);
      break;
  }
}

test.describe(`Journey: ${JOURNEY_CONFIG.name}`, () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(JOURNEY_CONFIG.baseUrl);
  });

  test('completes full journey successfully', async ({ page }) => {
    const results: { step: string; duration: number; status: string }[] = [];

    for (const step of JOURNEY_CONFIG.steps) {
      const startTime = Date.now();

      await test.step(step.name, async () => {
        // Wait for step to load
        await page.waitForSelector(step.waitFor, { timeout: 10000 });

        // Run assertions first
        for (const assertion of step.assertions) {
          await executeAssertion(page, assertion);
        }

        // Execute actions
        for (const action of step.actions) {
          await executeAction(page, action);
        }
      });

      results.push({
        step: step.name,
        duration: Date.now() - startTime,
        status: 'passed'
      });
    }

    // Log journey summary
    console.log('\n📊 Journey Summary:');
    console.log('═'.repeat(50));
    results.forEach(r => {
      console.log(`✅ ${r.step}: ${r.duration}ms`);
    });
    console.log('═'.repeat(50));
    console.log(`Total steps: ${results.length}`);
    console.log(`Total time: ${results.reduce((a, b) => a + b.duration, 0)}ms`);
  });

  // Individual step tests for debugging
  JOURNEY_CONFIG.steps.forEach((step, index) => {
    test(`Step ${index + 1}: ${step.name}`, async ({ page }) => {
      // Navigate through previous steps to reach this one
      for (let i = 0; i < index; i++) {
        const prevStep = JOURNEY_CONFIG.steps[i];
        await page.waitForSelector(prevStep.waitFor);
        for (const action of prevStep.actions) {
          await executeAction(page, action);
        }
      }

      // Test current step
      await page.waitForSelector(step.waitFor);

      for (const assertion of step.assertions) {
        await executeAssertion(page, assertion);
      }

      for (const action of step.actions) {
        await executeAction(page, action);
      }
    });
  });
});
