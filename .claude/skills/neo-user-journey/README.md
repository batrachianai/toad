# Neo User Journey

Elite UX agency skill for Claude Code. Delivers top 1% output—not generic AI aesthetics.

## Installation

### Option 1: Download the .skill file
Download `ux-journey-architect.skill` from [Releases](https://github.com/Cornjebus/neo-user-journey/releases) and copy to:

```bash
# Global installation
cp ux-journey-architect.skill ~/.claude/skills/

# Project-specific
cp ux-journey-architect.skill .claude/skills/
```

### Option 2: Clone the repository
```bash
git clone https://github.com/Cornjebus/neo-user-journey.git ~/.claude/skills/ux-journey-architect
```

## Features

### Anti-Generic AI Design
Guards against the patterns that make AI-generated UX feel soulless:
- Excessive emojis and decorative elements
- Verbose copy when concise works better
- Generic rounded corners and gradients everywhere
- One-size-fits-all aesthetics regardless of brand

### User Journey Creation
Create comprehensive journey maps with:
- Actions, touchpoints, and emotional mapping
- Multiple output formats (Mermaid, HTML, Markdown, Figma JSON)
- Pain points and opportunity identification

### Playwright Testing Suite
Four levels of automated testing:

| Script | Purpose |
|--------|---------|
| `journey-happy-path.spec.ts` | Validates primary user flow |
| `cognitive-walkthrough.spec.ts` | Measures timing, confusion, task completion |
| `accessibility-audit.spec.ts` | WCAG AA compliance via axe-core |
| `synthetic-user-test.spec.ts` | Simulates 7 different user personas |

### Synthetic User Personas
Test your product through the eyes of:
- **Impatient Power User** - Expects efficiency, skips tutorials
- **Confused First-Timer** - Needs guidance at every step
- **Accessibility-Dependent** - Keyboard-only, screen reader
- **Skeptical Evaluator** - Looking for reasons to reject
- **Distracted Mobile User** - One-handed, interrupted
- **Privacy-Conscious** - Minimal data sharing
- **International User** - Non-US formats and context

### Design Critique
Expert-level feedback using:
- Nielsen's 10 Usability Heuristics (with scoring)
- Cognitive load assessment
- Fitts's Law analysis
- Accessibility compliance
- Brand consistency

### Pattern Library
50+ proven UX patterns with success data:
- Onboarding (7 patterns with conversion rates)
- Checkout optimization (Baymard Institute research)
- Form design best practices
- Navigation patterns
- Empty states, loading states, error handling

### Research Integration
Tiered research sources:
- **Tier 1**: Nielsen Norman Group, Baymard Institute, Gov.uk Design System
- **Tier 2**: Amplitude, Mixpanel, CXL, industry reports
- **Tier 3**: Apple HIG, Material Design, WCAG

## Usage

The skill triggers on discussions involving:
- User journeys / flows
- UX research or design
- Design critique / feedback
- Usability testing
- Accessibility audits
- Persona creation
- Microcopy / UI copy

### Example Prompts

```
"Create a user journey for our checkout flow"
"Critique this login page design"
"Run synthetic user tests on our onboarding"
"What UX patterns work best for onboarding?"
"Audit this page for accessibility"
```

## Philosophy

Inspired by brands that create cult followings: **Apple, Noom, Hers**

- Every pixel serves a purpose
- Restraint over decoration
- Brand voice permeates every interaction
- Friction is intentionally designed (or removed)
- Emotional journey matters as much as functional journey

Before any design decision: *"Would IDEO or Pentagram do this, or is this lazy AI output?"*

## Structure

```
ux-journey-architect/
├── SKILL.md                    # Main skill definition
├── references/
│   ├── ANTI-PATTERNS.md        # What to avoid
│   ├── PATTERN-LIBRARY.md      # Proven UX patterns
│   ├── HEURISTICS.md           # Nielsen's 10 + scoring
│   ├── EMOTIONAL-MAPPING.md    # Emotional journey guide
│   ├── PERSONA-TEMPLATES.md    # 7 synthetic personas
│   ├── CRITIQUE-FRAMEWORK.md   # Critique methodology
│   └── RESEARCH-SOURCES.md     # Tiered research sources
├── scripts/
│   ├── journey-happy-path.spec.ts
│   ├── cognitive-walkthrough.spec.ts
│   ├── accessibility-audit.spec.ts
│   ├── synthetic-user-test.spec.ts
│   └── journey-export.py
└── assets/
    └── sample-journey.json
```

## Requirements

- Claude Code CLI
- Node.js (for Playwright tests)
- `@axe-core/playwright` (for accessibility testing)

```bash
npm install @playwright/test @axe-core/playwright
```

## License

MIT
