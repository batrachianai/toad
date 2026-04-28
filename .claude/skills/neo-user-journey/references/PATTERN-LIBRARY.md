# UX Pattern Library

Proven patterns with success data. Reference these, don't blindly copy.

## Table of Contents
1. [Onboarding Patterns](#onboarding-patterns)
2. [Checkout & Conversion](#checkout--conversion)
3. [Form Design](#form-design)
4. [Navigation](#navigation)
5. [Empty States](#empty-states)
6. [Loading States](#loading-states)
7. [Error Handling](#error-handling)
8. [Mobile Patterns](#mobile-patterns)

---

## Onboarding Patterns

### 1. Progressive Onboarding
**What**: Teach features in context, when user needs them
**Success rate**: 75% higher feature adoption vs front-loaded tours (Appcues data)
**When to use**: Complex products, power-user features
**Example**: Figma shows shortcuts when you perform actions manually

### 2. Single-Action Signup
**What**: One field (email) to start, collect details later
**Success rate**: Up to 60% conversion improvement (Sumo research)
**When to use**: Low-commitment products, free tiers
**Example**: Superhuman email-only waitlist

### 3. Value-First Demo
**What**: Let users experience core value before account creation
**Success rate**: 30% higher conversion (ProductLed benchmarks)
**When to use**: Products where value is immediately demonstrable
**Example**: Canva lets you design before signup

### 4. Social Proof Onboarding
**What**: Show what similar users achieved during signup
**Success rate**: 12-15% lift (various A/B tests)
**When to use**: Outcomes-based products
**Example**: Noom shows "Users like you lost X lbs"

### 5. Checklist Progress
**What**: Visible checklist of setup tasks
**Success rate**: 90% completion when under 5 items (Twilio research)
**When to use**: Required setup steps
**Example**: Notion new workspace setup

### 6. Persona-Based Paths
**What**: Different onboarding flows based on user type
**Success rate**: 25% better retention (Amplitude data)
**When to use**: Products serving distinct user types
**Example**: Slack asks "What brings you here?"

### 7. Empty State Guidance
**What**: First screen shows exactly what to do, not empty dashboard
**Success rate**: 50% faster time-to-value (internal studies)
**When to use**: All products
**Example**: Linear shows "Create your first issue" prominently

---

## Checkout & Conversion

*Source: Baymard Institute (2024), 49 guidelines from 19 years of research*

### Guest Checkout
**Impact**: 35% of users abandon if forced to create account
**Implementation**: Always offer guest checkout. Offer account creation AFTER purchase.

### Progress Indicator
**Impact**: Reduces anxiety, sets expectations
**Implementation**: 3-5 steps max. Show current step clearly. Steps should be: Cart → Shipping → Payment → Review

### Form Field Reduction
**Impact**: Each field removed = ~3% conversion increase
**Implementation**: Audit every field. "Company name" rarely needed. Single name field vs first/last.

### Trust Signals
**Impact**: 17% abandon due to payment security concerns
**Implementation**: Show security badges near payment. Display accepted cards. SSL indicators.

### Cart Persistence
**Impact**: Users return within 24 hours to complete 35% of abandoned carts
**Implementation**: Save cart to localStorage minimum. Email recovery for known users.

### Shipping Transparency
**Impact**: 48% abandon due to unexpected shipping costs
**Implementation**: Show shipping estimate early. Free shipping threshold visible.

### Payment Options
**Impact**: 9% abandon if preferred payment unavailable
**Implementation**: Cards, PayPal, Apple/Google Pay minimum. BNPL for high-ticket.

---

## Form Design

### Inline Validation
**Pattern**: Validate as user completes each field, not on submit
**Why**: Immediate feedback reduces errors by 22%
**Implementation**: Green checkmark for valid, red with specific message for invalid

### Smart Defaults
**Pattern**: Pre-fill likely values
**Why**: Reduces friction, speeds completion
**Examples**: Country from IP, date defaults to today, toggle defaults to common choice

### Input Masking
**Pattern**: Format inputs as user types (phone, card numbers)
**Why**: Prevents format errors, improves scanability
**Implementation**: Use library like Cleave.js or input-mask

### Error Messages
**Pattern**: Specific, actionable, positioned near field
**Why**: "Invalid input" tells user nothing
**Good**: "Password needs at least 8 characters (you have 6)"
**Bad**: "Password invalid"

### Single Column
**Pattern**: One field per row, top to bottom
**Why**: 15% faster completion vs multi-column (CXL research)
**Exception**: Short related fields (City/State/Zip)

### Optional Field Marking
**Pattern**: Mark optional fields, not required ones
**Why**: Reduces visual noise since most fields are required
**Implementation**: Gray "(optional)" text after label

---

## Navigation

### Persistent Primary Nav
**Pattern**: Main navigation always visible
**Why**: Orientation, quick access, reduces lost users
**Implementation**: Top bar or left sidebar. Never auto-hide primary nav.

### Breadcrumbs
**Pattern**: Show path from home to current page
**Why**: Orientation, easy backtracking, SEO benefit
**When**: Hierarchical content, e-commerce, docs
**Implementation**: Home > Category > Subcategory > Current

### Tab Navigation
**Pattern**: Tabs for switching views of same content
**Why**: Keeps user in context, clear relationship
**When**: Related content types, settings categories
**Rules**: Max 5-7 tabs, never nest tabs

### Hamburger Menu
**Pattern**: Hidden navigation behind icon
**Why**: Screen real estate on mobile
**Caveat**: Reduces discoverability. Primary actions should be visible.
**Data**: Items in hamburger get 50% less engagement

### Search
**Pattern**: Prominent search for content-heavy products
**Why**: Power users prefer search, 30% of users try search first
**Implementation**: Keyboard shortcut (Cmd+K), recent searches, suggestions

---

## Empty States

### First-Run Empty State
**Purpose**: Guide user to first action
**Elements**: Illustration (optional), clear headline, single primary CTA
**Example**: "Create your first project" with button

### No Results Empty State
**Purpose**: Explain why empty, suggest next steps
**Elements**: Explain what was searched, suggest alternatives, clear filters option
**Example**: "No results for 'xyz'. Try different keywords or browse categories."

### User-Cleared Empty State
**Purpose**: Confirm action, suggest next steps
**Elements**: Confirm items removed, suggest what to do next
**Example**: "All done! Your inbox is empty."

### Error Empty State
**Purpose**: Explain problem, offer recovery
**Elements**: What went wrong, how to fix, retry action
**Example**: "Couldn't load projects. Check your connection and try again."

---

## Loading States

### Skeleton Screens
**Pattern**: Show page structure with gray placeholders
**Why**: Perceived 30% faster than spinners
**When**: Known content structure
**Implementation**: Match actual content layout, animate shimmer

### Progressive Loading
**Pattern**: Load critical content first, defer rest
**Why**: Users can start engaging immediately
**Implementation**: Above-fold first, images lazy-load, non-critical async

### Optimistic UI
**Pattern**: Show expected result immediately, sync in background
**Why**: Feels instant
**When**: High-confidence actions (liking, saving, simple edits)
**Caveat**: Must handle failures gracefully

### Progress Indicators
**Pattern**: Show determinate progress for long operations
**Why**: Sets expectations, reduces abandonment
**When**: File uploads, long processes
**Implementation**: Percentage or step count, not just spinner

---

## Error Handling

### Prevention Over Correction
**Pattern**: Prevent errors before they happen
**Examples**: Disable submit until form valid, confirm destructive actions, autosave

### Graceful Degradation
**Pattern**: Partial functionality beats complete failure
**Example**: Image upload fails? Let user continue without image and retry later.

### Specific Error Messages
**Pattern**: Tell user exactly what went wrong and how to fix
**Bad**: "An error occurred"
**Good**: "Your session expired. Please log in again."

### Non-Blocking Errors
**Pattern**: Errors shouldn't stop all user activity
**Implementation**: Toast notifications for minor errors, inline for form errors
**Caveat**: Truly blocking errors (no auth, no network) can be full-page

### Error Recovery Paths
**Pattern**: Always give user a way forward
**Elements**: What happened, why, what to do now
**Example**: "Payment failed. Your card was declined. Try a different card or contact your bank."

---

## Mobile Patterns

### Thumb Zone Design
**Pattern**: Primary actions in easy thumb reach (bottom of screen)
**Data**: 75% of users use phone one-handed
**Implementation**: Bottom navigation, FABs, action sheets from bottom

### Touch Target Size
**Pattern**: Minimum 44x44 points for touch targets
**Why**: Smaller = missed taps, frustration
**Implementation**: Padding counts toward touch target, not just visible element

### Swipe Actions
**Pattern**: Swipe to reveal actions on list items
**When**: Common actions on lists (delete, archive, edit)
**Caveat**: Needs discoverability hint; not all users know to swipe

### Pull-to-Refresh
**Pattern**: Pull down to refresh content
**When**: Time-sensitive content, feeds
**Implementation**: Visual feedback during pull, loading indicator during refresh

### Bottom Sheets
**Pattern**: Slide-up panels from bottom of screen
**When**: Secondary actions, filters, options
**Why**: Easier to reach than top modals, can be partially dismissed
