# Anti-Patterns: What Makes Generic AI UX Bad

## Table of Contents
1. [Visual Anti-Patterns](#visual-anti-patterns)
2. [Copy Anti-Patterns](#copy-anti-patterns)
3. [Interaction Anti-Patterns](#interaction-anti-patterns)
4. [Architecture Anti-Patterns](#architecture-anti-patterns)

---

## Visual Anti-Patterns

### The "AI Gradient" Problem
**Pattern**: Purple-to-blue gradients, excessive blur effects, floating orbs
**Why it's bad**: Signals "AI made this" instantly. No brand differentiation.
**Fix**: Use brand colors. If no brand exists, choose a distinctive palette. Restraint over decoration.

### Rounded Corner Overload
**Pattern**: border-radius: 24px on everything
**Why it's bad**: Loses visual hierarchy. Everything feels the same weight.
**Fix**: Vary corner radius intentionally. Sharp corners = importance/action. Soft corners = secondary.

### Emoji Pollution
**Pattern**: Bullet points replaced with emojis, decorative emojis in headers
**Why it's bad**: Feels unserious, cluttered, tries too hard
**Fix**: Use emojis only when they add meaning (reactions, status indicators). Never decorative.

### Generic Hero Sections
**Pattern**: "Welcome to [Product]" + gradient background + generic illustration
**Why it's bad**: Zero differentiation. Users have seen this 10,000 times.
**Fix**: Lead with value proposition. Show the product. Be specific.

### Stock Illustration Syndrome
**Pattern**: Flat vector illustrations of "diverse people collaborating"
**Why it's bad**: Generic, forgettable, doesn't build brand
**Fix**: Custom imagery, product screenshots, or no imagery at all

---

## Copy Anti-Patterns

### Verbose Onboarding
**Pattern**: "Let's get you started! First, we'll need to collect some information..."
**Why it's bad**: Users want to do, not read. Every word is friction.
**Fix**: Reduce copy by 50%, then 50% again. Show, don't tell.

### Exclamation Point Abuse
**Pattern**: "Welcome! You're all set! Here's what's next!"
**Why it's bad**: Forced enthusiasm feels fake. Tiring to read.
**Fix**: Reserve exclamation points for genuine moments of delight.

### Corporate Jargon
**Pattern**: "Leverage our robust solution to optimize your workflow"
**Why it's bad**: Meaningless. Users tune it out.
**Fix**: Speak like a human. "Get more done" beats "optimize your workflow."

### Hedging Language
**Pattern**: "This might help you..." "You may want to consider..."
**Why it's bad**: Lacks confidence. Users want guidance, not suggestions.
**Fix**: Be direct. "Do this" not "You might want to do this."

### Feature Lists Over Benefits
**Pattern**: "Our product has: Real-time sync, Cloud storage, Collaboration tools"
**Why it's bad**: Features don't explain why users should care.
**Fix**: Lead with outcomes. "Never lose your work" beats "Cloud storage."

---

## Interaction Anti-Patterns

### Modal Hell
**Pattern**: Modals for everything—welcome, tooltips, confirmation, upsells
**Why it's bad**: Interrupts flow. Users click through without reading.
**Fix**: Inline guidance. Modals only for critical decisions.

### Hover-Dependent UI
**Pattern**: Important actions only visible on hover
**Why it's bad**: Invisible = nonexistent for most users. Fails on mobile.
**Fix**: Always-visible primary actions. Hover for secondary.

### Mystery Meat Navigation
**Pattern**: Icon-only navigation without labels
**Why it's bad**: Users guess meanings. Increases cognitive load.
**Fix**: Labels on all navigation items. Icons supplement, don't replace.

### Infinite Scroll Without Orientation
**Pattern**: Endless content with no sense of progress or location
**Why it's bad**: Users feel lost. Can't return to specific items.
**Fix**: Pagination, section markers, or "jump to" controls.

### Form Field Bloat
**Pattern**: Asking for 15 fields when 3 would suffice
**Why it's bad**: Each field is friction. Drop-off increases linearly.
**Fix**: Ask only what's immediately necessary. Progressive disclosure for the rest.

---

## Architecture Anti-Patterns

### Everything-on-Dashboard
**Pattern**: Dashboard showing every possible metric and action
**Why it's bad**: Overwhelming. Nothing stands out when everything does.
**Fix**: Curate ruthlessly. What does user need NOW? Hide the rest.

### Settings Sprawl
**Pattern**: Settings page with 50+ options in a flat list
**Why it's bad**: Users can't find what they need. Feels complex.
**Fix**: Group logically. Progressive disclosure. Smart defaults.

### Feature Dumping
**Pattern**: Every feature accessible from every screen
**Why it's bad**: Increases cognitive load. Dilutes focus.
**Fix**: Context-aware features. Show what's relevant to current task.

### Notification Overload
**Pattern**: Notifications for every possible event
**Why it's bad**: Users disable all notifications. Signal becomes noise.
**Fix**: Default to minimal. Let users opt into more.

### Onboarding That Teaches Everything
**Pattern**: 10-step onboarding tour covering all features
**Why it's bad**: Users retain nothing. Delays the "aha" moment.
**Fix**: Get users to value immediately. Teach features when relevant.

---

## The Test

Before shipping, ask:

1. **Would a human designer at Apple/IDEO do this?**
2. **Does this decision serve the user or fill space?**
3. **If I removed this element, would anyone notice?**
4. **Does this look like every other AI-generated site?**

If any answer is "no" or "yes" (for #3 and #4), reconsider.
