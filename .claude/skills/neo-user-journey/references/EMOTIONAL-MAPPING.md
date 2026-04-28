# Emotional Journey Mapping

## Table of Contents
1. [Why Emotions Matter](#why-emotions-matter)
2. [Emotional States Framework](#emotional-states-framework)
3. [Mapping Methodology](#mapping-methodology)
4. [Common Emotional Patterns](#common-emotional-patterns)
5. [Design Interventions](#design-interventions)

---

## Why Emotions Matter

- Users don't remember features; they remember how products made them *feel*
- Emotional peaks and endings disproportionately influence perception (Peak-End Rule)
- Negative emotions cause abandonment; positive emotions create loyalty
- Cult-following brands (Apple, Noom, Hers) obsess over emotional design

**Key insight**: A functionally perfect product that feels frustrating will lose to an imperfect product that feels delightful.

---

## Emotional States Framework

### Primary UX Emotions

| Emotion | Trigger | Risk | Opportunity |
|---------|---------|------|-------------|
| **Confident** | Clear guidance, progress | None—maintain it | Reinforce with celebration |
| **Curious** | Interesting content, mystery | Confusion if overdone | Drive exploration |
| **Delighted** | Unexpected value, polish | Sets high expectations | Create memorable moments |
| **Neutral** | Routine tasks | Forgettable experience | Opportunity for delight |
| **Uncertain** | Ambiguous choices, no feedback | Abandonment | Add clarity, guidance |
| **Frustrated** | Errors, friction, confusion | Churn, negative word-of-mouth | Fix immediately |
| **Anxious** | High-stakes actions (payment, delete) | Abandonment | Reassure, confirm |
| **Disappointed** | Unmet expectations | Churn | Reset expectations earlier |

### Intensity Scale (for mapping)

```
+3  Delighted / Excited
+2  Pleased / Satisfied
+1  Content / Comfortable
 0  Neutral
-1  Uncertain / Mildly frustrated
-2  Frustrated / Anxious
-3  Angry / Defeated
```

---

## Mapping Methodology

### Step 1: Define Journey Stages
Break the experience into discrete stages. Common structure:

1. **Awareness** → First encounter with product
2. **Consideration** → Evaluating whether to try
3. **Acquisition** → Signup/purchase
4. **Activation** → First meaningful use
5. **Engagement** → Ongoing use
6. **Retention** → Returning over time
7. **Advocacy** → Recommending to others

### Step 2: Identify Touchpoints
For each stage, list specific interactions:
- Screens/pages viewed
- Actions taken
- Messages received
- Decisions made

### Step 3: Map Emotions
For each touchpoint, assess:
- **Expected emotion**: What should user feel?
- **Likely emotion**: What do they probably feel?
- **Evidence**: Why do you think this? (data, research, intuition)

### Step 4: Identify Gaps
Where expected ≠ likely, you have a problem to solve.

### Step 5: Design Interventions
For each negative gap, propose specific solutions.

---

## Journey Map Template

```markdown
## [Journey Name]: [User Type]

### Stage: [Name]
**Goal**: What user is trying to accomplish
**Touchpoints**: Specific interactions

| Touchpoint | Action | Emotion (+3 to -3) | Pain Points | Opportunities |
|------------|--------|-------------------|-------------|---------------|
| [Screen/interaction] | [What user does] | [+/-X: emotion name] | [Friction] | [Improvement ideas] |

### Emotional Graph
[Use ASCII or Mermaid to visualize emotion over time]

     +3 |          *
     +2 |    *         *
     +1 |  *             *
      0 |*                 *
     -1 |                    *
     -2 |                      *
        -------------------------
          A  B  C  D  E  F  G  H

A: First visit, B: Signup, C: Onboarding...
```

---

## Common Emotional Patterns

### The Onboarding Valley
**Pattern**: Excitement at signup → frustration during setup → satisfaction after first success
**Risk**: Users quit in the valley
**Solution**: Shorten setup, provide early win, show progress

```
Emotion
   +2  *                              *
   +1    *                          *
    0      *                      *
   -1        *    *    *    *  *
   -2          *
        Signup → Setup → Learning → First Win
```

### The Anxiety Spike
**Pattern**: Smooth flow → anxiety at high-stakes moment (payment, commit, delete)
**Risk**: Abandonment at critical conversion point
**Solution**: Reassurance, reversibility, social proof at anxiety peak

### The Feature Discovery Delight
**Pattern**: Routine use → unexpected useful feature → increased engagement
**Risk**: Feature never discovered
**Solution**: Contextual revelation, not upfront feature dumping

### The Error Frustration Cliff
**Pattern**: Building engagement → error/failure → sharp negative drop
**Risk**: Disproportionate impact on overall perception (negativity bias)
**Solution**: Graceful error handling, quick recovery, over-communicate

---

## Design Interventions by Emotion

### For Uncertainty
- Add progress indicators
- Provide explicit next steps
- Show examples of success
- Reduce choices (paradox of choice)
- Add inline help/tooltips

### For Frustration
- Identify and remove friction
- Improve error messages
- Add undo functionality
- Reduce required fields
- Provide escape hatches

### For Anxiety
- Show security indicators
- Emphasize reversibility ("You can change this later")
- Add social proof
- Break into smaller commitments
- Confirm before destructive actions

### For Neutral (opportunity to delight)
- Add micro-animations
- Personalize content
- Celebrate milestones
- Surprise with value
- Polish transitions

### For Disappointment
- Set accurate expectations earlier
- Provide alternatives when primary path fails
- Acknowledge the gap
- Offer compensation/recovery

---

## Peak-End Rule Application

Users remember:
1. The **most intense** moment (peak)
2. The **final** moment (end)

**Design implications**:
- Engineer a positive peak (delight moment)
- Never end on negative (error, rejection)
- Make endings feel complete (confirmation, celebration)
- If there must be friction, put it in the middle

**Examples**:
- IKEA: Exhausting shopping → cheap hot dog at end = positive memory
- Apple: Unboxing experience = engineered peak
- Noom: Daily weigh-in celebration = repeated positive peaks
