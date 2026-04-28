# Design Critique Framework

Expert-level feedback methodology. Be direct, specific, and actionable.

## Table of Contents
1. [Critique Principles](#critique-principles)
2. [Structured Critique Process](#structured-critique-process)
3. [Visual Design Checklist](#visual-design-checklist)
4. [Interaction Design Checklist](#interaction-design-checklist)
5. [Copy & Content Checklist](#copy--content-checklist)
6. [Critique Output Template](#critique-output-template)

---

## Critique Principles

### Be Direct
- Don't: "This is great, but maybe consider..."
- Do: "The CTA is invisible. Users won't find it."

### Be Specific
- Don't: "The form needs work"
- Do: "The form has 12 fields but only 4 are needed for signup"

### Be Actionable
- Don't: "This feels off"
- Do: "Increase CTA button size from 32px to 44px minimum for touch"

### Prioritize
- Blocking issues first (prevents task completion)
- Usability issues second (causes difficulty)
- Polish issues last (nice to have)

### Reference Principles
- Cite specific heuristics: "Violates Nielsen #6: Recognition over recall"
- Reference patterns: "Standard checkout uses 3-5 steps, this has 8"
- Use data when available: "48% of users abandon due to unexpected shipping costs"

---

## Structured Critique Process

### Step 1: Understand Intent (30 seconds)
- What is this screen/flow trying to accomplish?
- Who is the target user?
- What is the primary action?

### Step 2: First Impression Scan (30 seconds)
Without analyzing, note:
- Where does your eye go first?
- What feels confusing?
- What stands out (good or bad)?

### Step 3: Systematic Evaluation (3-5 minutes)
Use checklists below for:
- Visual design
- Interaction design
- Copy & content

### Step 4: Prioritize Findings
Categorize each issue:
- **P0 - Blocking**: Prevents task completion
- **P1 - Major**: Causes significant difficulty
- **P2 - Minor**: Annoyance, workaround exists
- **P3 - Polish**: Nice to fix, low impact

### Step 5: Provide Solutions
For each P0/P1 issue, provide:
- What's wrong
- Why it matters
- How to fix it

---

## Visual Design Checklist

### Hierarchy
- [ ] Primary action is visually dominant
- [ ] Secondary actions are visually subordinate
- [ ] Information hierarchy matches importance
- [ ] Eye flow follows natural reading pattern (F or Z)

### Typography
- [ ] Body text is 16px+ (mobile: 16px minimum)
- [ ] Line height is 1.4-1.6 for body text
- [ ] Maximum line length is 60-80 characters
- [ ] Headings create clear document structure
- [ ] Font weights differentiate hierarchy (not just size)

### Color
- [ ] Color contrast meets WCAG AA (4.5:1 for text)
- [ ] Color is not the only way to convey meaning
- [ ] Palette is limited (3-5 colors max)
- [ ] Accent color draws attention to right places
- [ ] Error states use conventional colors (red)

### Spacing
- [ ] Consistent spacing system (8px grid recommended)
- [ ] Related items are grouped (proximity principle)
- [ ] Adequate whitespace for breathing room
- [ ] Padding inside elements is proportional

### Layout
- [ ] Clear alignment (left-aligned text in western locales)
- [ ] Responsive behavior is intentional
- [ ] Nothing feels cramped or lost
- [ ] Visual balance across the composition

### Brand
- [ ] Consistent with brand identity
- [ ] Doesn't feel generic/template-like
- [ ] Appropriate tone for the brand

---

## Interaction Design Checklist

### Affordances
- [ ] Clickable things look clickable
- [ ] Disabled states are visually distinct
- [ ] Hover states indicate interactivity
- [ ] Form fields look like inputs

### Feedback
- [ ] Actions have immediate visual response
- [ ] Loading states are shown
- [ ] Errors are surfaced near the problem
- [ ] Success is confirmed

### Navigation
- [ ] User knows where they are
- [ ] User knows where they can go
- [ ] Primary navigation is visible
- [ ] Back/cancel is always available

### Forms
- [ ] Labels are visible (not placeholder-only)
- [ ] Required fields are marked
- [ ] Validation is inline and immediate
- [ ] Error messages are specific

### Touch/Click Targets
- [ ] Touch targets are 44×44pt minimum
- [ ] Adequate spacing between targets
- [ ] Primary actions are easy to reach (thumb zone on mobile)

### Accessibility
- [ ] Focus states are visible
- [ ] Tab order is logical
- [ ] Screen reader would make sense
- [ ] Can be used keyboard-only

---

## Copy & Content Checklist

### Clarity
- [ ] Language is simple and jargon-free
- [ ] Sentences are short (under 20 words)
- [ ] Paragraphs are scannable
- [ ] Instructions are unambiguous

### Action
- [ ] CTAs are verb-first ("Get started" not "Getting started")
- [ ] CTAs describe the outcome
- [ ] Next steps are always clear

### Tone
- [ ] Matches brand voice
- [ ] Appropriate for context
- [ ] Consistent throughout

### Error Messages
- [ ] Explain what went wrong
- [ ] Use plain language (not error codes)
- [ ] Suggest how to fix
- [ ] Don't blame the user

### Microcopy
- [ ] Empty states guide to action
- [ ] Loading messages set expectations
- [ ] Confirmation messages are clear
- [ ] Help text is helpful (not redundant)

---

## Critique Output Template

```markdown
# Design Critique: [Screen/Flow Name]

## Overview
**Purpose**: [What this is trying to accomplish]
**Target User**: [Who uses this]
**Primary Action**: [What user should do]

## First Impressions
[2-3 sentences on immediate reaction]

## Critical Issues (P0-P1)

### Issue 1: [Name]
**Severity**: P0/P1
**Heuristic**: [Which principle is violated]
**Problem**: [What's wrong]
**Impact**: [Why it matters]
**Fix**: [How to solve it]

### Issue 2: [Name]
...

## Minor Issues (P2-P3)
- [P2] [Brief description] → [Quick fix]
- [P3] [Brief description] → [Quick fix]

## What's Working Well
- [Positive observation 1]
- [Positive observation 2]

## Summary
[2-3 sentences on overall assessment and top priorities]
```

---

## Example Critique

### Bad Critique (avoid this)
> "This looks nice overall! I think the form might be a bit long but it's probably fine. Maybe consider making the button a different color? Just a thought!"

### Good Critique (do this)
> **P0 - Form Abandonment Risk**: The signup form has 14 fields, but only email/password are needed to create an account. Each additional field increases abandonment by ~3% (Baymard). **Fix**: Reduce to email + password. Collect profile info after signup via progressive profiling.
>
> **P1 - CTA Visibility**: The "Create Account" button uses gray text on light gray background (contrast ratio 2.1:1). Fails WCAG AA and is easy to miss. **Fix**: Use primary brand color, ensure 4.5:1 contrast minimum.
