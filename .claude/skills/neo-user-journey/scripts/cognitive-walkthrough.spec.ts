/**
 * Cognitive Walkthrough Test Template
 *
 * Evaluates usability from a user's perspective by measuring:
 * - Task completion time
 * - Number of clicks/interactions
 * - Error encounters
 * - Confusion points (hesitation, backtracking)
 *
 * Usage:
 *   npx playwright test cognitive-walkthrough.spec.ts
 */

import { test, expect, type Page, type Locator } from '@playwright/test';

// ============================================================================
// CONFIGURATION
// ============================================================================

const WALKTHROUGH_CONFIG = {
  name: 'New User First Task Completion',
  baseUrl: 'http://localhost:3000',

  // Task definition - what the user is trying to accomplish
  task: {
    description: 'Create a new project and add first item',
    successCriteria: '[data-testid="item-created-success"]',
    maxExpectedTime: 120000, // 2 minutes
    maxExpectedClicks: 10,
  },

  // Questions to evaluate at each step (Wharton cognitive walkthrough)
  evaluationQuestions: [
    'Will the user try to achieve the right effect?',
    'Will the user notice the correct action is available?',
    'Will the user associate the correct action with the effect?',
    'Will the user see progress is being made toward the goal?',
  ],

  // Track these potential confusion indicators
  confusionIndicators: {
    hesitationThreshold: 5000, // ms of inactivity = hesitation
    backtrackingPatterns: ['goBack', 'navigate back', 'cancel', 'close'],
    errorPatterns: ['error', 'invalid', 'failed', 'wrong'],
  }
};

// ============================================================================
// METRICS TRACKING
// ============================================================================

interface WalkthroughMetrics {
  taskName: string;
  startTime: number;
  endTime: number;
  totalDuration: number;
  clickCount: number;
  keystrokeCount: number;
  hesitationCount: number;
  hesitationDurations: number[];
  backtrackCount: number;
  errorCount: number;
  errorMessages: string[];
  steps: StepMetric[];
  success: boolean;
}

interface StepMetric {
  name: string;
  timestamp: number;
  duration: number;
  clicksInStep: number;
  hesitations: number;
}

class MetricsCollector {
  private metrics: WalkthroughMetrics;
  private lastActionTime: number;
  private currentStepStart: number;
  private currentStepClicks: number;
  private currentStepHesitations: number;

  constructor(taskName: string) {
    this.metrics = {
      taskName,
      startTime: Date.now(),
      endTime: 0,
      totalDuration: 0,
      clickCount: 0,
      keystrokeCount: 0,
      hesitationCount: 0,
      hesitationDurations: [],
      backtrackCount: 0,
      errorCount: 0,
      errorMessages: [],
      steps: [],
      success: false,
    };
    this.lastActionTime = Date.now();
    this.currentStepStart = Date.now();
    this.currentStepClicks = 0;
    this.currentStepHesitations = 0;
  }

  recordClick(): void {
    this.checkForHesitation();
    this.metrics.clickCount++;
    this.currentStepClicks++;
    this.lastActionTime = Date.now();
  }

  recordKeystroke(): void {
    this.checkForHesitation();
    this.metrics.keystrokeCount++;
    this.lastActionTime = Date.now();
  }

  recordBacktrack(): void {
    this.metrics.backtrackCount++;
  }

  recordError(message: string): void {
    this.metrics.errorCount++;
    this.metrics.errorMessages.push(message);
  }

  checkForHesitation(): void {
    const timeSinceLastAction = Date.now() - this.lastActionTime;
    if (timeSinceLastAction > WALKTHROUGH_CONFIG.confusionIndicators.hesitationThreshold) {
      this.metrics.hesitationCount++;
      this.metrics.hesitationDurations.push(timeSinceLastAction);
      this.currentStepHesitations++;
    }
  }

  startStep(name: string): void {
    this.currentStepStart = Date.now();
    this.currentStepClicks = 0;
    this.currentStepHesitations = 0;
  }

  endStep(name: string): void {
    this.metrics.steps.push({
      name,
      timestamp: this.currentStepStart,
      duration: Date.now() - this.currentStepStart,
      clicksInStep: this.currentStepClicks,
      hesitations: this.currentStepHesitations,
    });
  }

  complete(success: boolean): WalkthroughMetrics {
    this.metrics.endTime = Date.now();
    this.metrics.totalDuration = this.metrics.endTime - this.metrics.startTime;
    this.metrics.success = success;
    return this.metrics;
  }

  getMetrics(): WalkthroughMetrics {
    return this.metrics;
  }
}

// ============================================================================
// TEST IMPLEMENTATION
// ============================================================================

test.describe(`Cognitive Walkthrough: ${WALKTHROUGH_CONFIG.name}`, () => {
  let collector: MetricsCollector;

  test.beforeEach(async ({ page }) => {
    collector = new MetricsCollector(WALKTHROUGH_CONFIG.task.description);

    // Set up interaction tracking
    await page.addInitScript(() => {
      document.addEventListener('click', () => {
        (window as any).__clickCount = ((window as any).__clickCount || 0) + 1;
      });
      document.addEventListener('keydown', () => {
        (window as any).__keystrokeCount = ((window as any).__keystrokeCount || 0) + 1;
      });
    });

    // Monitor console for errors
    page.on('console', msg => {
      if (msg.type() === 'error') {
        collector.recordError(msg.text());
      }
    });

    await page.goto(WALKTHROUGH_CONFIG.baseUrl);
  });

  test('measures task completion metrics', async ({ page }) => {
    const startTime = Date.now();

    // ========================================================================
    // STEP 1: Initial Page Load
    // ========================================================================
    collector.startStep('Page Load');

    // Check: Will the user notice the correct action is available?
    const primaryCTA = page.locator('[data-testid="primary-cta"], button:has-text("Get Started"), a:has-text("Start")').first();
    await expect(primaryCTA).toBeVisible({ timeout: 5000 });

    // Measure time to first interaction
    const timeToFirstInteraction = Date.now() - startTime;
    console.log(`⏱️  Time to first possible interaction: ${timeToFirstInteraction}ms`);

    collector.endStep('Page Load');

    // ========================================================================
    // STEP 2: Begin Task
    // ========================================================================
    collector.startStep('Begin Task');

    // Track click
    collector.recordClick();
    await primaryCTA.click();

    collector.endStep('Begin Task');

    // ========================================================================
    // STEP 3: Form/Input Phase (customize for your flow)
    // ========================================================================
    collector.startStep('Form Completion');

    // Look for form elements
    const formInputs = page.locator('input:visible, textarea:visible, select:visible');
    const inputCount = await formInputs.count();

    if (inputCount > 0) {
      console.log(`📝 Found ${inputCount} form inputs`);

      // Fill required fields (customize selectors)
      const emailField = page.locator('[type="email"], [name="email"]').first();
      if (await emailField.isVisible()) {
        collector.recordClick();
        await emailField.fill('test@example.com');
        collector.recordKeystroke();
      }
    }

    collector.endStep('Form Completion');

    // ========================================================================
    // STEP 4: Submit/Complete Action
    // ========================================================================
    collector.startStep('Submit Action');

    const submitButton = page.locator('[type="submit"], button:has-text("Submit"), button:has-text("Create")').first();
    if (await submitButton.isVisible()) {
      collector.recordClick();
      await submitButton.click();
    }

    collector.endStep('Submit Action');

    // ========================================================================
    // STEP 5: Verify Success
    // ========================================================================
    collector.startStep('Verify Success');

    let success = false;
    try {
      await page.waitForSelector(WALKTHROUGH_CONFIG.task.successCriteria, { timeout: 10000 });
      success = true;
    } catch {
      // Check for error messages
      const errorVisible = await page.locator('[role="alert"], .error, [data-testid*="error"]').isVisible();
      if (errorVisible) {
        const errorText = await page.locator('[role="alert"], .error, [data-testid*="error"]').first().textContent();
        collector.recordError(errorText || 'Unknown error');
      }
    }

    collector.endStep('Verify Success');

    // ========================================================================
    // GENERATE REPORT
    // ========================================================================
    const metrics = collector.complete(success);

    console.log('\n' + '═'.repeat(60));
    console.log('📊 COGNITIVE WALKTHROUGH REPORT');
    console.log('═'.repeat(60));
    console.log(`Task: ${metrics.taskName}`);
    console.log(`Status: ${metrics.success ? '✅ COMPLETED' : '❌ FAILED'}`);
    console.log('─'.repeat(60));
    console.log('TIMING');
    console.log(`  Total Duration: ${metrics.totalDuration}ms (${(metrics.totalDuration / 1000).toFixed(1)}s)`);
    console.log(`  Expected Max: ${WALKTHROUGH_CONFIG.task.maxExpectedTime}ms`);
    console.log(`  ${metrics.totalDuration <= WALKTHROUGH_CONFIG.task.maxExpectedTime ? '✅' : '⚠️'} ${metrics.totalDuration <= WALKTHROUGH_CONFIG.task.maxExpectedTime ? 'Within target' : 'EXCEEDED TARGET'}`);
    console.log('─'.repeat(60));
    console.log('INTERACTIONS');
    console.log(`  Total Clicks: ${metrics.clickCount}`);
    console.log(`  Expected Max: ${WALKTHROUGH_CONFIG.task.maxExpectedClicks}`);
    console.log(`  ${metrics.clickCount <= WALKTHROUGH_CONFIG.task.maxExpectedClicks ? '✅' : '⚠️'} ${metrics.clickCount <= WALKTHROUGH_CONFIG.task.maxExpectedClicks ? 'Within target' : 'TOO MANY CLICKS'}`);
    console.log(`  Keystrokes: ${metrics.keystrokeCount}`);
    console.log('─'.repeat(60));
    console.log('CONFUSION INDICATORS');
    console.log(`  Hesitations (>${WALKTHROUGH_CONFIG.confusionIndicators.hesitationThreshold}ms pause): ${metrics.hesitationCount}`);
    if (metrics.hesitationDurations.length > 0) {
      console.log(`  Avg Hesitation: ${Math.round(metrics.hesitationDurations.reduce((a, b) => a + b, 0) / metrics.hesitationDurations.length)}ms`);
    }
    console.log(`  Backtrack Actions: ${metrics.backtrackCount}`);
    console.log(`  Errors Encountered: ${metrics.errorCount}`);
    if (metrics.errorMessages.length > 0) {
      metrics.errorMessages.forEach(e => console.log(`    - ${e}`));
    }
    console.log('─'.repeat(60));
    console.log('STEP BREAKDOWN');
    metrics.steps.forEach((step, i) => {
      console.log(`  ${i + 1}. ${step.name}`);
      console.log(`     Duration: ${step.duration}ms | Clicks: ${step.clicksInStep} | Hesitations: ${step.hesitations}`);
    });
    console.log('═'.repeat(60));

    // Assertions
    expect(metrics.success).toBe(true);
    expect(metrics.totalDuration).toBeLessThan(WALKTHROUGH_CONFIG.task.maxExpectedTime);
    expect(metrics.clickCount).toBeLessThan(WALKTHROUGH_CONFIG.task.maxExpectedClicks * 2); // Allow 2x tolerance
  });

  test('evaluates clarity of each step', async ({ page }) => {
    // For each major step, evaluate cognitive walkthrough questions
    const evaluations: { step: string; question: string; pass: boolean; notes: string }[] = [];

    // Evaluate initial state
    const hasClearCTA = await page.locator('button, a[href]').filter({ hasText: /start|begin|create|sign up/i }).count() > 0;
    evaluations.push({
      step: 'Landing',
      question: WALKTHROUGH_CONFIG.evaluationQuestions[1], // Will user notice correct action?
      pass: hasClearCTA,
      notes: hasClearCTA ? 'Clear CTA visible' : 'No obvious starting point',
    });

    // Check for progress indicators
    const hasProgress = await page.locator('[role="progressbar"], .progress, .step-indicator, [data-step]').count() > 0;
    evaluations.push({
      step: 'Flow',
      question: WALKTHROUGH_CONFIG.evaluationQuestions[3], // Will user see progress?
      pass: hasProgress,
      notes: hasProgress ? 'Progress indicator present' : 'No progress indication',
    });

    console.log('\n📋 COGNITIVE EVALUATION');
    console.log('═'.repeat(50));
    evaluations.forEach(e => {
      console.log(`${e.pass ? '✅' : '❌'} ${e.step}: ${e.question}`);
      console.log(`   ${e.notes}`);
    });
  });
});
