# Synthetic User Personas for Testing

Use these personas to simulate how different user types would experience a flow. Each persona has distinct behaviors, patience levels, and needs.

## Table of Contents
1. [Testing Personas](#testing-personas)
2. [Persona Testing Methodology](#persona-testing-methodology)
3. [Custom Persona Template](#custom-persona-template)

---

## Testing Personas

### 1. Impatient Power User ("Alex")

**Profile**:
- Expert with similar products
- Expects efficiency, hates tutorials
- Will find shortcuts or leave

**Behaviors**:
- Skips all onboarding/instructions
- Looks for keyboard shortcuts immediately
- Tries to bulk-select, batch-edit
- Gets frustrated by required steps
- Abandons if anything feels slow

**Test questions**:
- Can Alex complete core task in under 60 seconds?
- Are there keyboard shortcuts for common actions?
- Can onboarding be skipped entirely?
- Do modals have keyboard dismiss (Esc)?
- Is there a "power user" path?

**Red flags for Alex**:
- Forced tutorials
- No keyboard navigation
- Slow animations that can't be skipped
- One-item-at-a-time workflows

---

### 2. Confused First-Timer ("Jordan")

**Profile**:
- Never used this type of product
- Needs guidance at every step
- Will abandon rather than figure it out

**Behaviors**:
- Reads all instructions carefully
- Hesitates before clicking anything
- Looks for help/support constantly
- Misunderstands jargon
- Takes screenshots "just in case"

**Test questions**:
- Is the first action obviously clear?
- Are all icons labeled?
- Is there contextual help available?
- Does terminology assume prior knowledge?
- Is there a clear "back" at every step?

**Red flags for Jordan**:
- Icon-only navigation
- Technical jargon
- No visible help option
- Ambiguous next steps
- No confirmation of actions

---

### 3. Accessibility-Dependent User ("Sam")

**Profile**:
- Uses screen reader (VoiceOver/NVDA)
- Keyboard-only navigation
- May have low vision, motor impairment, or cognitive differences

**Behaviors**:
- Tabs through interface linearly
- Relies on ARIA labels and headings
- Can't see hover states
- Needs adequate color contrast
- May use zoom up to 200%

**Test questions**:
- Can entire flow be completed keyboard-only?
- Are all interactive elements focusable?
- Do images have alt text?
- Is color contrast WCAG AA compliant?
- Does screen reader announce state changes?

**Red flags for Sam**:
- Click-only interactions
- Missing focus indicators
- Meaning conveyed by color alone
- Unlabeled form fields
- Time-limited actions without extension

---

### 4. Skeptical Evaluator ("Riley")

**Profile**:
- Evaluating product for team/company
- Looking for reasons to reject
- Comparing against competitors

**Behaviors**:
- Tests edge cases intentionally
- Looks for pricing catches
- Reads fine print, ToS
- Tries to break things
- Documents problems carefully

**Test questions**:
- What happens at the edges (0 items, 10000 items)?
- Is pricing transparent and fair?
- Are there hidden limitations?
- How does error handling look?
- What data is collected?

**Red flags for Riley**:
- Hidden pricing
- Features that don't work
- Poor error handling
- Unclear data practices
- "Contact sales" for basic info

---

### 5. Distracted Mobile User ("Casey")

**Profile**:
- Using phone one-handed
- Frequently interrupted
- Poor network connectivity possible

**Behaviors**:
- Uses thumb only (bottom of screen preference)
- Gets interrupted mid-flow
- Switches apps frequently
- Has limited attention span
- Types as little as possible

**Test questions**:
- Are primary actions in thumb zone?
- Is state preserved if user leaves and returns?
- Does it work on slow connections?
- Can forms be completed with autocomplete?
- Are touch targets at least 44×44pt?

**Red flags for Casey**:
- Important actions at top of screen
- No state persistence
- Large text inputs required
- Heavy assets on every page
- No offline tolerance

---

### 6. Privacy-Conscious User ("Morgan")

**Profile**:
- Minimal data sharing preferred
- Uses ad blockers, private browsing
- Skeptical of tracking

**Behaviors**:
- Declines optional data collection
- Looks for privacy policy
- Questions why info is needed
- Blocks cookies/trackers
- Uses fake data when possible

**Test questions**:
- Does product work with cookies disabled?
- Is data collection explained and optional?
- Can user complete flow with minimal info?
- Is there a clear privacy policy?
- What breaks with ad blockers?

**Red flags for Morgan**:
- Required social login only
- Unexplained data requests
- Tracking without consent
- No privacy policy link
- Breaks without trackers

---

### 7. International User ("Priya")

**Profile**:
- Non-native English speaker
- Different cultural context
- May have different name/address format

**Behaviors**:
- May misunderstand idioms
- Has name that doesn't fit First/Last format
- Address format differs from US
- Payment methods differ (no US cards)
- Date/number formats differ

**Test questions**:
- Is language simple and translatable?
- Do forms accept international formats?
- Are international payment methods supported?
- Is content culturally appropriate?
- Are dates/currencies/numbers localized?

**Red flags for Priya**:
- US-only address validation
- "Middle name required"
- Single name field rejecting short names
- US-centric payment only
- Cultural assumptions in content

---

## Persona Testing Methodology

### Quick Persona Test (5 min each)
1. Choose 3 personas most relevant to product
2. Walk through primary flow as each persona
3. Note friction points specific to that persona
4. Rank severity of issues found

### Full Persona Audit (30 min each)
1. Define specific task for persona to complete
2. Document every step and decision point
3. Rate emotional state at each step (-3 to +3)
4. List all friction points and blockers
5. Propose specific fixes

### Output Format
```markdown
## Persona Test: [Persona Name]

**Task**: [What they're trying to do]
**Result**: [Completed / Abandoned at X / Completed with difficulty]

### Journey
| Step | Action | Emotion | Notes |
|------|--------|---------|-------|
| 1 | Landed on homepage | 0 | Clear CTA visible |
| 2 | Clicked signup | +1 | Easy to find |
| 3 | Saw 10-field form | -2 | Too many required fields |
...

### Issues Found
1. [Severity X] [Issue description]
2. [Severity X] [Issue description]

### Recommendations
1. [Specific fix]
2. [Specific fix]
```

---

## Custom Persona Template

Create product-specific personas using this template:

```markdown
### [Persona Name] ("[Short Name]")

**Profile**:
- [Key characteristic 1]
- [Key characteristic 2]
- [Key characteristic 3]

**Demographics** (if relevant):
- Age range:
- Tech comfort:
- Context of use:

**Goals**:
- [Primary goal]
- [Secondary goal]

**Frustrations**:
- [What annoys them]
- [What makes them leave]

**Behaviors**:
- [How they interact with products]
- [Specific patterns]

**Test questions**:
- [Key question for this persona]
- [Key question for this persona]

**Red flags**:
- [What will cause them to abandon]
- [What will cause them to complain]
```
