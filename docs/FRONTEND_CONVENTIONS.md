# NestMate Frontend Conventions

> Version: 1.0  
> Applies to: `frontend/`  
> Stack: React + Vite + React Router + Plain CSS

This document defines the mandatory frontend coding conventions for NestMate.

The goals are:

- consistent JSX structure;
- predictable CSS organization;
- responsive layouts that do not depend on one screen size;
- clear separation between pages, feature components, layout components, and shared UI;
- maintainable code across Farm Owner, Technician, and Administrator;
- easier collaboration and code review.

---

# 1. General Principles

All frontend code MUST follow these principles:

1. Prefer clarity over cleverness.
2. A page must remain primarily a composition layer.
3. Business/feature UI belongs inside actor feature folders.
4. Reusable infrastructure belongs in shared folders.
5. CSS must be scoped to the relevant page or component.
6. Do not introduce global styling unless it is intentionally global.
7. Do not fix layout problems using arbitrary hard-coded values.
8. Components must work across supported viewport sizes.
9. Do not redesign already-approved UI while implementing unrelated changes.
10. New UI must follow the existing NestMate visual language unless a redesign is explicitly approved.

---

# 2. Frontend Folder Structure

NestMate follows this structure:

```text
src/
├── components/
│   ├── common/
│   ├── layout/
│   ├── ui/
│   │
│   └── features/
│       ├── farm-owner/
│       ├── technician/
│       ├── admin/
│       └── account/
│
├── pages/
│   ├── farm-owner/
│   ├── technician/
│   ├── admin/
│   └── account/
│
├── config/
├── context/
├── hooks/
├── services/
└── utils/
```

Actor-specific feature components MUST be placed under:

```text
src/components/features/<actor>/<feature>/
```

Example:

```text
src/components/features/technician/devices/
├── DeviceSummary.jsx
├── DeviceFilters.jsx
├── DeviceCard.jsx
├── DeviceDetailPanel.jsx
└── devicesMockData.js
```

Route-level pages belong under:

```text
src/pages/<actor>/<feature>/
```

Pages SHOULD remain thin and compose feature components.

---

# 3. JSX Semantic Structure

Use semantic HTML whenever an appropriate element exists.

Preferred hierarchy:

```text
main
├── header
├── nav
├── section
│   ├── header
│   └── content
├── article
└── footer
```

Example:

```jsx
function DevicesPage() {
  return (
    <AppLayout>
      <main className="technician-devices">
        <header className="technician-devices__header">
          <div>
            <span className="technician-devices__eyebrow">
              TECHNICAL OPERATIONS
            </span>

            <h1>Quản lý thiết bị</h1>

            <p>
              Theo dõi trạng thái và cấu hình thiết bị.
            </p>
          </div>

          <div className="technician-devices__actions">
            ...
          </div>
        </header>

        <section className="technician-devices__section">
          <header className="technician-devices__section-header">
            <div>
              <h2>Thiết bị đang hoạt động</h2>
              <p>Trạng thái thiết bị theo thời gian thực.</p>
            </div>
          </header>

          <div className="technician-devices__content">
            ...
          </div>
        </section>
      </main>
    </AppLayout>
  )
}
```

Do not use `<div>` for everything when semantic elements are appropriate.

Use:

- `<main>` for page content;
- `<header>` for page/section headers;
- `<section>` for functional groups;
- `<article>` for independent cards/items;
- `<nav>` for navigation and substantial tab groups;
- `<button>` for actions;
- `<a>` or router navigation for actual navigation.

Do not use clickable `<div>` elements when a button or link is appropriate.

---

# 4. Component Responsibility

A component SHOULD have one primary UI responsibility.

Good:

```text
DeviceSummary.jsx
DeviceFilters.jsx
DeviceCard.jsx
DeviceDetailPanel.jsx
```

Avoid excessively large components such as:

```text
TechnicianEverything.jsx
```

Also avoid meaningless over-fragmentation such as:

```text
Title.jsx
Subtitle.jsx
SmallDot.jsx
CardText.jsx
```

Create a component when it:

- represents a meaningful UI concept;
- is reused;
- contains meaningful behavior;
- substantially improves readability of its parent.

---

# 5. Page Responsibility

Pages SHOULD compose feature components rather than contain the entire feature implementation.

Preferred:

```jsx
function DevicesPage() {
  return (
    <AppLayout>
      <main className="technician-devices">
        <DevicePageHeader />
        <DeviceSummary />
        <DeviceFilters />
        <DeviceGrid />
      </main>
    </AppLayout>
  )
}
```

Avoid route pages growing into large files containing cards, tables, modals, mock data, icons, filters, and business logic together.

---

# 6. Class Naming

Use descriptive, feature-scoped class names.

NestMate uses a BEM-inspired convention:

```css
.device-card {}

.device-card__icon {}

.device-card__content {}

.device-card__status {}

.device-card__actions {}

.device-card--offline {}

.device-card--warning {}
```

Page-level classes should identify their actor or feature when useful:

```css
.owner-dashboard {}

.technician-devices {}

.admin-users {}
```

Avoid names based purely on current position:

```css
.left {}
.right {}
.top {}
.bottom {}
```

Avoid meaningless names:

```css
.box1 {}
.item2 {}
.card-new {}
.test {}
.container123 {}
```

Prefer role-based names:

```css
.device-card__actions
```

instead of:

```css
.device-card__right
```

---

# 7. Root Class Rule

Every substantial page/component MUST have an identifiable root class.

Example:

```jsx
<article className="device-card">
```

Its CSS should be scoped from that component:

```css
.device-card {}

.device-card__title {}

.device-card__status {}
```

Avoid deeply coupled DOM selectors:

```css
.page > div > div:nth-child(2) span {}
```

Small direct-child selectors are acceptable when structurally clear:

```css
.device-card > svg {}
```

---

# 8. CSS File Organization

CSS files SHOULD use the following section order when applicable:

```css
/* ========================================
   PAGE
   ======================================== */


/* ========================================
   HEADER
   ======================================== */


/* ========================================
   NAVIGATION / TABS
   ======================================== */


/* ========================================
   CONTENT
   ======================================== */


/* ========================================
   COMPONENT STATES
   ======================================== */


/* ========================================
   RESPONSIVE
   ======================================== */
```

Component-specific files may omit irrelevant sections.

Responsive rules MUST normally be grouped near the end of the file.

Do not scatter unrelated media queries throughout the stylesheet.

---

# 9. CSS Property Order

Properties inside selectors SHOULD follow this order.

## 9.1 Position

```css
position
z-index
inset
top
right
bottom
left
```

## 9.2 Size

```css
width
min-width
max-width
height
min-height
max-height
overflow
```

## 9.3 Layout

```css
display
grid-template-columns
grid-template-rows
grid-column
grid-row
flex
flex-direction
flex-wrap
align-items
align-content
justify-content
justify-items
gap
```

## 9.4 Spacing

```css
margin
padding
```

## 9.5 Border

```css
border
border-width
border-color
border-radius
```

## 9.6 Background

```css
background
background-color
background-image
```

## 9.7 Typography

```css
color
font-family
font-size
font-weight
line-height
letter-spacing
text-align
text-decoration
text-overflow
white-space
```

## 9.8 Visual Effects

```css
opacity
box-shadow
filter
backdrop-filter
transform
```

## 9.9 Interaction

```css
cursor
pointer-events
user-select
```

## 9.10 Animation

```css
transition
animation
```

Selectors do NOT need every category.

The rule only defines where a property belongs when it is used.

---

# 10. Static Sizes

Use fixed values only when the component logically requires a fixed size.

Appropriate:

```css
.icon-button {
  width: 40px;
  height: 40px;
}
```

Appropriate fixed-size elements include:

- icons;
- avatars;
- compact buttons;
- form controls where consistent height is intentional;
- thumbnails;
- controlled chart containers;
- controlled camera previews.

Content containers SHOULD normally adapt to their parent:

```css
.component {
  width: 100%;
  min-width: 0;
}
```

Do not randomly mix:

```css
width: 300px;
width: 25%;
width: 22vw;
```

for equivalent components without a layout reason.

Viewport units SHOULD NOT be used merely to repair broken layout.

---

# 11. Height Rules

Avoid fixed heights for content-driven components.

Avoid:

```css
.card {
  height: 173px;
}
```

when card content may grow.

Prefer:

```css
.card {
  min-height: 173px;
}
```

or allow content to determine the height.

Fixed heights are acceptable for intentionally controlled elements such as:

- buttons;
- inputs;
- avatars;
- icons;
- thumbnails;
- charts;
- camera previews.

---

# 12. Flex and Grid Safety

Any Grid/Flex child that may contain long content SHOULD be checked for:

```css
min-width: 0;
```

Example:

```css
.device-card__content {
  min-width: 0;
  flex: 1;
}
```

Only after layout is correct should text truncation be applied:

```css
.device-card__title {
  overflow: hidden;

  text-overflow: ellipsis;
  white-space: nowrap;
}
```

Do NOT use ellipsis to hide an incorrectly sized layout.

---

# 13. Grid Rules

Prefer Grid for two-dimensional layouts and Flexbox for one-dimensional alignment.

Preferred equal grid:

```css
.device-grid {
  display: grid;

  grid-template-columns:
    repeat(3, minmax(0, 1fr));

  gap: 16px;
}
```

When a real minimum width exists:

```css
.operations-grid {
  display: grid;

  grid-template-columns:
    minmax(0, 1.5fr)
    minmax(290px, 0.7fr);

  gap: 16px;
}
```

Do not force too many columns into insufficient space.

If content begins to collapse, change the grid at an appropriate breakpoint.

---

# 14. Standard Breakpoints

New NestMate frontend code SHOULD use these breakpoints:

```text
Desktop                  > 1280px
Small desktop/tablet     <= 1280px
Tablet landscape         <= 1000px
Tablet                   <= 800px
Mobile                   <= 600px
Small mobile             <= 430px
```

Example:

```css
@media (max-width: 1280px) {
}

@media (max-width: 1000px) {
}

@media (max-width: 800px) {
}

@media (max-width: 600px) {
}

@media (max-width: 430px) {
}
```

Do not introduce arbitrary breakpoints such as:

```css
@media (max-width: 1173px)
@media (max-width: 943px)
@media (max-width: 723px)
```

unless the component has a documented reason.

Existing legacy breakpoints may be normalized during refactoring.

---

# 15. Responsive Design Rule

Responsive behavior is part of component completion.

A component is NOT considered complete merely because it looks correct at the developer's current viewport.

At minimum, verify:

- desktop;
- reduced desktop/tablet;
- mobile.

Prefer layouts that naturally adapt before adding media queries.

---

# 16. Typography

Do NOT change the global project font without an explicit design decision.

The existing global rule remains authoritative:

```css
body {
  font-family: Arial, sans-serif;
}
```

Feature/page typography may use local font stacks where already established, but global typography must not be silently replaced.

Avoid arbitrary font-size proliferation.

Preferred approximate scale:

```text
9px       metadata / very small labels
10px      captions
11px      secondary compact UI
12px      normal compact UI
13-14px   card headings
16-18px   section headings
28-40px   major page headings
```

Exceptions are allowed when visually justified.

---

# 17. Colors

Do not continuously introduce slightly different colors for equivalent semantic purposes.

For example, avoid accumulating multiple near-identical navy values without reason.

Colors should eventually be represented by shared design tokens such as:

```css
:root {
  --color-navy-900: #102e4a;
  --color-gold-600: #b97818;
  --color-cream-100: #faf7ef;

  --color-success: #38a876;
  --color-warning: #d0932f;
  --color-danger: #c85b4e;

  --color-text: #102e4a;
  --color-text-muted: #8796a3;

  --border-soft: rgba(16, 45, 70, 0.07);
}
```

Do NOT perform a project-wide token migration as part of an unrelated feature.

Token migration should be performed deliberately during frontend refactoring.

---

# 18. Inline Styles

Presentation SHOULD live in CSS.

Avoid:

```jsx
<div
  style={{
    width: '100%',
    padding: '20px',
    color: '#102e4a',
  }}
>
```

Inline styles are acceptable for genuinely dynamic values.

Example:

```jsx
<div
  className="progress-bar__value"
  style={{ width: `${percentage}%` }}
/>
```

---

# 19. CSS Scope

Do not add broad selectors from feature stylesheets such as:

```css
button {}

input {}

h2 {}

section {}
```

Prefer scoped selectors:

```css
.technician-devices button {}

.device-filter input {}
```

Global rules belong only in intentionally global stylesheets.

---

# 20. Shared vs Feature CSS

Use shared CSS only for truly shared infrastructure.

Examples:

```text
components/layout/
components/common/
components/ui/
```

Actor-specific styles stay with the actor feature/page.

Do not move styles into global CSS merely to make them easier to access.

---

# 21. CSS File Splitting

NestMate does NOT require one CSS file per JSX file.

This is valid:

```text
devices/
├── DeviceCard.jsx
├── DeviceFilters.jsx
├── DeviceDetailPanel.jsx
├── devices.css
└── devicesMockData.js
```

A complex component may have its own stylesheet:

```text
DeviceDetailPanel.jsx
DeviceDetailPanel.css
```

Split files according to maintainability, not an arbitrary one-to-one rule.

---

# 22. Mock Data

Mock data SHOULD be separated from substantial UI components.

Preferred:

```text
devices/
├── DeviceCard.jsx
├── DeviceSummary.jsx
└── devicesMockData.js
```

Do not scatter the same mock domain data across multiple components.

Mock data is temporary and should be structured so Backend/API integration can replace its source without requiring UI redesign.

---

# 23. State and Behavior

Keep state as close as practical to the feature that owns it.

Do not create global Context for state that is only used by one component/page.

Use Context for genuinely shared application state such as authentication.

Backend integration should replace mock data sources rather than forcing component redesign whenever possible.

---

# 24. UI States

Interactive components SHOULD consider applicable states:

```text
default
hover
focus-visible
active
disabled
loading
empty
error
offline
warning
success
```

Not every component requires every state.

Keyboard focus SHOULD remain visible for interactive controls.

---

# 25. Existing Approved UI

When fixing an existing approved page:

- fix the identified problem;
- avoid unrelated redesign;
- avoid global style changes;
- avoid changing typography across the application;
- avoid changing established spacing/color language without approval.

Refactoring and redesign are separate activities.

---

# 26. Reference Project Rule

Before implementing a substantial NestMate feature:

1. read the NestMate requirement/SRS;
2. inspect the corresponding reference implementation when available;
3. identify what is relevant;
4. remove reference functionality outside NestMate scope;
5. implement using NestMate architecture and visual language.

The reference project is a guide, not the authoritative scope.

NestMate requirements remain authoritative.

If a material deviation from the reference is proposed, document:

1. reference approach;
2. proposed NestMate approach;
3. benefit or necessity;
4. trade-offs or risks.

Material deviations should be agreed before implementation.

---

# 27. Responsive Completion Checklist

Before declaring a UI feature complete:

```text
[ ] No unintended horizontal overflow
[ ] Grid/Flex children do not collapse unexpectedly
[ ] Important text is not accidentally truncated
[ ] Desktop layout works
[ ] <= 1280px layout works
[ ] <= 1000px layout remains usable
[ ] <= 800px layout remains usable
[ ] <= 600px layout remains usable
[ ] Interactive controls remain accessible
```

Testing every pixel width is not required.

The component must remain structurally sound across the supported ranges.

---

# 28. Feature Completion Checklist

Before committing a frontend feature:

```text
[ ] Matches approved requirement/scope
[ ] Reference checked where applicable
[ ] Correct actor/feature folder
[ ] Page remains reasonably thin
[ ] JSX uses meaningful semantic structure
[ ] Classes follow naming convention
[ ] CSS is scoped
[ ] CSS property order is consistent
[ ] No unnecessary magic dimensions
[ ] Flex/Grid children use min-width: 0 where required
[ ] No unnecessary inline styles
[ ] No unintended global overrides
[ ] Responsive behavior checked
[ ] Existing approved UI not unintentionally changed
[ ] Browser console has no new critical errors
[ ] npm run build passes
```

---

# 29. Git Workflow

Frontend work follows actor-level branches or another explicitly agreed large-flow branch.

Within that branch:

```text
small completed feature
        ↓
test
        ↓
meaningful commit
        ↓
next feature
```

Do NOT create a pull request for every small UI feature.

When the complete actor flow is ready:

```text
all actor features complete
        ↓
final review
        ↓
responsive review
        ↓
npm run build
        ↓
push
        ↓
one actor-level PR to main
```

Commit messages should describe meaningful changes.

Examples:

```text
feat(FE): add owner farm management
feat(FE): add shared account settings
feat(FE): enhance header and notification experience
fix(FE): correct owner dashboard responsive layout
refactor(FE): normalize owner frontend styles
```

---

# 30. Rule for AI-Assisted Development

Any AI assistant generating or modifying NestMate frontend code MUST:

1. respect the current SRS and approved project scope;
2. inspect the reference implementation when required;
3. preserve approved UI unless redesign is requested;
4. follow this document;
5. avoid introducing new architecture conventions silently;
6. avoid broad global CSS changes during isolated feature work;
7. provide responsive layouts rather than screenshot-specific layouts;
8. prefer whole-file replacements when requested by the project owner;
9. keep code discoverable by actor and feature;
10. distinguish feature implementation from later refactoring.

Before presenting frontend code, verify:

```text
[ ] Requirement
[ ] Reference
[ ] Scope
[ ] Folder ownership
[ ] Semantic JSX
[ ] Class naming
[ ] CSS scope
[ ] Property order
[ ] Flex/Grid safety
[ ] Responsive behavior
[ ] No accidental global changes
```

---

# 31. Core Rule

A UI component is not complete merely because it looks correct in one screenshot.

It is complete when:

- its structure is understandable;
- its CSS is maintainable;
- its content can change safely;
- its layout remains stable across supported screen sizes;
- it fits the NestMate architecture;
- it does not create unnecessary side effects elsewhere.