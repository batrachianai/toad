# Textual CSS Styling Guide

Complete guide to styling Textual applications with TCSS (Textual CSS).

## CSS Basics

### Inline Styles

Define styles directly in widget class:
```python
class MyWidget(Widget):
    DEFAULT_CSS = """
    MyWidget {
        background: $primary;
        color: $text;
        border: solid $accent;
    }
    """
```

### External Stylesheets

Load from file:
```python
class MyApp(App):
    CSS_PATH = "app.tcss"  # Load from app.tcss file
```

### Multiple Stylesheets

Load multiple files:
```python
class MyApp(App):
    CSS_PATH = ["base.tcss", "theme.tcss", "overrides.tcss"]
```

## Selectors

### Type Selectors

Target widget types:
```css
Button {
    background: blue;
}

Label {
    color: white;
}
```

### ID Selectors

Target specific widgets:
```css
#submit-button {
    background: green;
}

#error-message {
    color: red;
}
```

### Class Selectors

Target classes:
```css
.highlight {
    background: yellow;
    color: black;
}

.card {
    border: solid white;
    padding: 1;
}
```

### Pseudo-classes

Target widget states:
```css
Button:hover {
    background: lighten($primary, 20%);
}

Button:focus {
    border: thick $accent;
}

Input:focus {
    border: solid $success;
}

/* Disabled state */
Button:disabled {
    opacity: 50%;
}
```

### Descendant Selectors

Target nested widgets:
```css
/* Any Label inside a Container */
Container Label {
    color: gray;
}

/* Direct children only */
Container > Label {
    color: white;
}

/* Specific nesting */
#sidebar .menu-item {
    padding: 1;
}
```

### Multiple Selectors

Apply same style to multiple targets:
```css
Button, Input, Select {
    border: solid $accent;
}

.error, .warning {
    font-weight: bold;
}
```

## Colors

### Semantic Colors

Use theme colors:
```css
Widget {
    background: $background;
    color: $text;
    border: solid $primary;
}

/* Available semantic colors */
$primary         /* Primary theme color */
$secondary       /* Secondary theme color */
$accent          /* Accent color */
$background      /* Background color */
$surface         /* Surface color */
$panel           /* Panel color */
$text            /* Primary text color */
$text-muted      /* Muted text */
$text-disabled   /* Disabled text */
$success         /* Success state */
$warning         /* Warning state */
$error           /* Error state */
$boost           /* Highlight color */
```

### Color Formats

Define custom colors:
```css
Widget {
    background: #1e3a8a;              /* Hex */
    color: rgb(255, 255, 255);        /* RGB */
    border-color: rgba(255, 0, 0, 0.5); /* RGBA with alpha */
}

/* Named colors */
Widget {
    background: transparent;
    color: black;
    border-color: white;
}
```

### Color Functions

Manipulate colors:
```css
Widget {
    background: darken($primary, 20%);
    color: lighten($text, 10%);
    border-color: fade($accent, 50%);
}
```

## Typography

### Text Style

```css
Label {
    text-style: bold;          /* bold, italic, underline */
    text-style: bold italic;   /* Multiple styles */
    text-style: reverse;       /* Reverse colors */
    text-style: strike;        /* Strikethrough */
}
```

### Text Alignment

```css
Label {
    text-align: left;    /* left, center, right, justify */
}
```

### Text Opacity

```css
Label {
    text-opacity: 70%;   /* Semi-transparent text */
}
```

## Borders

### Border Styles

```css
Widget {
    border: solid $accent;      /* Solid border */
    border: dashed blue;        /* Dashed */
    border: heavy green;        /* Heavy */
    border: double white;       /* Double */
    border: thick $primary;     /* Thick */
    border: none;               /* No border */
}
```

### Border Sides

```css
Widget {
    border-top: solid red;
    border-right: dashed blue;
    border-bottom: thick green;
    border-left: double white;
}
```

### Border Title

```css
Widget {
    border: solid $accent;
    border-title-align: center;  /* left, center, right */
}
```

## Dimensions

### Width

```css
Widget {
    width: 40;        /* Fixed columns */
    width: 50%;       /* Percentage of parent */
    width: 1fr;       /* Fractional unit */
    width: auto;      /* Size to content */
}
```

### Height

```css
Widget {
    height: 20;       /* Fixed rows */
    height: 100%;     /* Full parent height */
    height: auto;     /* Size to content */
}
```

### Min/Max Constraints

```css
Widget {
    min-width: 20;
    max-width: 80;
    min-height: 10;
    max-height: 50;
}
```

## Spacing

### Padding

Space inside widget:
```css
Widget {
    padding: 1;              /* All sides */
    padding: 1 2;            /* Vertical Horizontal */
    padding: 1 2 3 4;        /* Top Right Bottom Left */
}

/* Individual sides */
Widget {
    padding-top: 1;
    padding-right: 2;
    padding-bottom: 1;
    padding-left: 2;
}
```

### Margin

Space outside widget:
```css
Widget {
    margin: 1;
    margin: 0 2;
    margin: 1 2 1 2;
}

/* Individual sides */
Widget {
    margin-top: 1;
    margin-right: 2;
}
```

## Layout Properties

### Display

Control visibility:
```css
Widget {
    display: block;     /* Visible */
    display: none;      /* Hidden */
}
```

### Visibility

Alternative to display:
```css
Widget {
    visibility: visible;
    visibility: hidden;   /* Hidden but takes space */
}
```

### Opacity

Transparency:
```css
Widget {
    opacity: 100%;      /* Fully opaque */
    opacity: 50%;       /* Semi-transparent */
    opacity: 0%;        /* Fully transparent */
}
```

### Layout Type

```css
Container {
    layout: vertical;    /* Stack vertically */
    layout: horizontal;  /* Stack horizontally */
    layout: grid;        /* Grid layout */
}
```

### Grid Properties

```css
Container {
    layout: grid;
    grid-size: 3 2;         /* 3 columns, 2 rows */
    grid-gutter: 1 2;       /* Vertical Horizontal gaps */
    grid-rows: 10 auto 1fr; /* Row sizes */
    grid-columns: 1fr 2fr;  /* Column sizes */
}

/* Grid item spanning */
Widget {
    column-span: 2;    /* Span 2 columns */
    row-span: 3;       /* Span 3 rows */
}
```

### Alignment

```css
Container {
    align: center middle;     /* Horizontal Vertical */
    align-horizontal: left;   /* left, center, right */
    align-vertical: top;      /* top, middle, bottom */
}

/* Content alignment */
Container {
    content-align: center middle;
    content-align-horizontal: right;
    content-align-vertical: bottom;
}
```

### Scrollbars

```css
Widget {
    overflow: auto;       /* Show scrollbars when needed */
    overflow: scroll;     /* Always show scrollbars */
    overflow: hidden;     /* No scrollbars */
}

/* Individual axes */
Widget {
    overflow-x: auto;
    overflow-y: scroll;
}

/* Scrollbar styling */
Widget {
    scrollbar-background: $panel;
    scrollbar-color: $primary;
    scrollbar-color-hover: $accent;
    scrollbar-color-active: $boost;
}
```

## Effects

### Transitions

Animate property changes:
```css
Button {
    background: blue;
    transition: background 300ms;
}

Button:hover {
    background: lightblue;  /* Animates over 300ms */
}

/* Multiple properties */
Widget {
    transition: background 200ms, border 150ms;
}
```

### Offset

Position adjustment:
```css
Widget {
    offset: 1 2;      /* X Y offset */
    offset-x: 1;
    offset-y: 2;
}
```

### Layer

Z-index equivalent:
```css
Widget {
    layer: above;     /* Higher layer */
    layer: below;     /* Lower layer */
}
```

## Docking

Pin widgets to edges:
```css
#header {
    dock: top;
    height: 3;
}

#sidebar {
    dock: left;
    width: 30;
}

#footer {
    dock: bottom;
    height: 3;
}
```

## Theme Variables

Define reusable values:
```css
/* Define variables */
Screen {
    --card-bg: #1e3a8a;
    --card-border: white;
    --card-padding: 1 2;
}

/* Use variables */
.card {
    background: var(--card-bg);
    border: solid var(--card-border);
    padding: var(--card-padding);
}
```

## Complete Theme Example

```css
/* app.tcss */

/* Theme colors */
Screen {
    background: #0f172a;
    color: #e2e8f0;
}

/* Headers */
Header {
    background: #1e293b;
    color: #60a5fa;
    dock: top;
    height: 3;
}

Footer {
    background: #1e293b;
    color: #94a3b8;
    dock: bottom;
    height: 1;
}

/* Buttons */
Button {
    background: #3b82f6;
    color: white;
    border: none;
    margin: 0 1;
    padding: 0 2;
    min-width: 16;
    transition: background 200ms;
}

Button:hover {
    background: #60a5fa;
}

Button:focus {
    border: solid #93c5fd;
}

Button.-primary {
    background: #10b981;
}

Button.-primary:hover {
    background: #34d399;
}

Button.-error {
    background: #ef4444;
}

Button.-error:hover {
    background: #f87171;
}

/* Inputs */
Input {
    border: solid #475569;
    background: #1e293b;
    color: #e2e8f0;
    padding: 0 1;
}

Input:focus {
    border: solid #3b82f6;
}

/* Containers */
.card {
    background: #1e293b;
    border: solid #334155;
    padding: 1 2;
    margin: 1;
}

.card > .title {
    text-style: bold;
    color: #60a5fa;
    margin-bottom: 1;
}

/* Data tables */
DataTable {
    background: #1e293b;
}

DataTable > .datatable--header {
    background: #334155;
    color: #60a5fa;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #3b82f6;
}

/* Scrollbars */
*::-webkit-scrollbar {
    scrollbar-background: #1e293b;
    scrollbar-color: #475569;
}

*::-webkit-scrollbar:hover {
    scrollbar-color: #64748b;
}
```

## Dark/Light Themes

Support theme switching:
```python
class MyApp(App):
    ENABLE_DARK_MODE = True
    
    CSS = """
    /* Dark theme (default) */
    Screen {
        background: #0f172a;
        color: #e2e8f0;
    }
    
    /* Light theme */
    Screen.light {
        background: #f8fafc;
        color: #1e293b;
    }
    """
    
    def action_toggle_theme(self) -> None:
        self.dark = not self.dark
```

## Responsive Styles

Conditional styles based on size:
```css
/* Default (small screens) */
#sidebar {
    width: 100%;
}

/* Medium screens */
Screen:width-gt-80 #sidebar {
    width: 30;
}

/* Large screens */
Screen:width-gt-120 #sidebar {
    width: 40;
}
```

## Best Practices

1. **Use semantic colors** - Prefer `$primary` over hardcoded values
2. **Organize CSS** - Group related styles together
3. **Use classes** - Reusable styles via classes, not IDs
4. **Minimize specificity** - Avoid overly specific selectors
5. **Use transitions** - Smooth state changes
6. **Test both themes** - Ensure dark/light compatibility
7. **Keep CSS DRY** - Use variables for repeated values
8. **Document custom variables** - Comment non-obvious choices

## Debugging Styles

View computed styles:
```python
def on_mount(self) -> None:
    widget = self.query_one("#my-widget")
    self.log(widget.styles)  # Log all computed styles
```

Use Textual devtools:
```bash
textual run --dev app.py
# Press F1 to view CSS inspector
```

Temporary debugging borders:
```css
* {
    border: solid red;  /* See all widget boundaries */
}
```
