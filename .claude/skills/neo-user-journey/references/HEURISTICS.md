# Usability Heuristics & Evaluation Frameworks

## Table of Contents
1. [Nielsen's 10 Usability Heuristics](#nielsens-10-usability-heuristics)
2. [Scoring Methodology](#scoring-methodology)
3. [Cognitive Load Principles](#cognitive-load-principles)
4. [Fitts's Law](#fittss-law)
5. [Accessibility Quick Checks](#accessibility-quick-checks)

---

## Nielsen's 10 Usability Heuristics

*Jakob Nielsen, 1994. Still the gold standard.*

### 1. Visibility of System Status
**Principle**: Keep users informed about what's happening through appropriate feedback within reasonable time.

**Check for**:
- Loading indicators during async operations
- Confirmation of user actions (save, submit, delete)
- Progress indicators for multi-step processes
- Current location in navigation (breadcrumbs, active states)
- Form validation feedback

**Score 0-4**: 0=Never informs, 1=Rarely, 2=Sometimes, 3=Usually, 4=Always clear feedback

### 2. Match Between System and Real World
**Principle**: Speak the user's language, not system-speak. Follow real-world conventions.

**Check for**:
- Familiar terminology (not jargon)
- Logical order of information
- Recognizable icons and metaphors
- Cultural appropriateness
- Domain-appropriate language

**Score 0-4**: 0=Pure tech jargon, 1=Mostly confusing, 2=Mixed, 3=Mostly clear, 4=Natural language

### 3. User Control and Freedom
**Principle**: Users need a clear "emergency exit" to leave unwanted states without extended dialogue.

**Check for**:
- Undo/redo functionality
- Cancel buttons on forms and modals
- Clear navigation back to safety
- Easy way to clear filters/search
- Exit from long processes

**Score 0-4**: 0=Trapped frequently, 1=Difficult exits, 2=Some exits, 3=Usually escapable, 4=Always in control

### 4. Consistency and Standards
**Principle**: Users shouldn't have to wonder whether different words, situations, or actions mean the same thing.

**Check for**:
- Consistent terminology throughout
- Same actions produce same results
- Platform conventions followed
- Visual consistency (colors, typography, spacing)
- Consistent interaction patterns

**Score 0-4**: 0=Inconsistent everywhere, 1=Many inconsistencies, 2=Some consistency, 3=Mostly consistent, 4=Fully consistent

### 5. Error Prevention
**Principle**: Better than good error messages is a design that prevents problems in the first place.

**Check for**:
- Confirmation before destructive actions
- Constraints that prevent invalid input
- Smart defaults
- Clear labels that prevent mistakes
- Autosave and draft recovery

**Score 0-4**: 0=Errors easy to make, 1=Few safeguards, 2=Some prevention, 3=Good prevention, 4=Errors nearly impossible

### 6. Recognition Rather Than Recall
**Principle**: Minimize memory load by making objects, actions, and options visible.

**Check for**:
- Visible options (not hidden in menus)
- Contextual help when needed
- Recent items and history
- Autocomplete suggestions
- Labels on icons

**Score 0-4**: 0=Heavy memorization needed, 1=Much recall required, 2=Some recognition aids, 3=Good recognition, 4=Everything discoverable

### 7. Flexibility and Efficiency of Use
**Principle**: Accelerators—unseen by novice—may speed up interaction for expert users.

**Check for**:
- Keyboard shortcuts
- Customizable interface
- Recent items / favorites
- Bulk actions
- Power user features that don't complicate basics

**Score 0-4**: 0=One way only, 1=Limited flexibility, 2=Some shortcuts, 3=Good accelerators, 4=Highly flexible

### 8. Aesthetic and Minimalist Design
**Principle**: Dialogues should not contain information that is irrelevant or rarely needed.

**Check for**:
- Only necessary information visible
- Clear visual hierarchy
- Purposeful use of color/emphasis
- No decorative clutter
- Focused, uncluttered layouts

**Score 0-4**: 0=Overwhelming clutter, 1=Too much noise, 2=Some clutter, 3=Mostly clean, 4=Perfectly minimal

### 9. Help Users Recognize, Diagnose, and Recover from Errors
**Principle**: Error messages should be expressed in plain language, indicate the problem, and suggest a solution.

**Check for**:
- Plain language error messages (not codes)
- Specific problem identification
- Actionable recovery suggestions
- Errors shown near the problem
- Non-blocking error handling

**Score 0-4**: 0=Cryptic errors, 1=Vague errors, 2=Clear but unhelpful, 3=Clear with suggestions, 4=Perfect recovery paths

### 10. Help and Documentation
**Principle**: Help should be easy to search, focused on tasks, list concrete steps, and not be too large.

**Check for**:
- Searchable help/documentation
- Contextual help (tooltips, inline hints)
- Task-focused organization
- Concise, scannable content
- Easy access without leaving context

**Score 0-4**: 0=No help, 1=Hard to find/use, 2=Basic help exists, 3=Good documentation, 4=Excellent contextual help

---

## Scoring Methodology

### Heuristic Audit Score
**Total possible**: 40 points (10 heuristics × 4 points max)

| Score Range | Rating | Action |
|-------------|--------|--------|
| 36-40 | Excellent | Minor polish only |
| 28-35 | Good | Address weak areas |
| 20-27 | Acceptable | Significant improvements needed |
| 12-19 | Poor | Major UX overhaul required |
| 0-11 | Critical | Unusable, complete redesign |

### Severity Rating for Individual Issues
| Severity | Description | Priority |
|----------|-------------|----------|
| 4 - Catastrophic | Prevents task completion | Fix immediately |
| 3 - Major | Significant difficulty | Fix before release |
| 2 - Minor | Annoyance but workaround exists | Fix when possible |
| 1 - Cosmetic | Polish issue | Fix if time permits |
| 0 - Not a problem | False positive | Ignore |

---

## Cognitive Load Principles

### Types of Cognitive Load

**Intrinsic Load**: Complexity inherent to the task
- Can't eliminate, but can structure information
- Break complex tasks into steps
- Provide scaffolding

**Extraneous Load**: Caused by poor design
- ELIMINATE THIS
- Confusing navigation, unclear labels, visual clutter
- Every bit of extraneous load = failure

**Germane Load**: Effort spent learning/understanding
- Good load—leads to mastery
- Support with progressive disclosure
- Reward with efficiency gains

### Cognitive Load Checklist

- [ ] Can user complete primary task without distraction?
- [ ] Is information presented in digestible chunks?
- [ ] Are related items grouped together?
- [ ] Is visual hierarchy clear (what's important)?
- [ ] Can user focus on one thing at a time?
- [ ] Are decisions minimized or simplified?
- [ ] Is working memory load reasonable (≤4 items)?

---

## Fitts's Law

**The larger a target and the closer it is, the faster and easier it is to hit.**

`Time = a + b × log2(1 + D/W)`

Where D = distance to target, W = width of target

### Practical Applications

1. **Make important buttons large**: CTAs should be visually prominent AND large enough to click easily

2. **Put primary actions near starting position**: Don't make users travel across the screen

3. **Use screen edges**: Edges are "infinitely deep"—users can slam cursor to edge. Good for menus.

4. **Group related actions**: Reduces travel distance between common sequences

5. **Consider touch targets**: Mobile needs minimum 44×44 pt touch targets

### Common Violations
- Tiny "X" buttons to close modals
- Text links instead of buttons for primary actions
- Important actions in corners far from content
- Hover menus that require precise mouse movement
