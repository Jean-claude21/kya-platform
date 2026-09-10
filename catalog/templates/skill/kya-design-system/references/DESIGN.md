## Overview

KYA-Platform is the governed digital control plane of KYA-Energy Group. Its visual world is a **precision energy workshop**: calm, exact, fluid, and truthful about operational state. Employees use it to find and activate authorized applications, MCP connectors, Skills, data products, and shared methods. Authorized operators use a separate administration layer to govern organization, identities, KYA Core, systems of record, publication, secrets, and audit.

The interface uses a warm operational canvas (`{colors.warm-ground}` — #f7f6f1), white work surfaces (`{colors.surface}` — #ffffff), and deep teal structure (`{colors.deep-teal}` — #063d3a). The official KYA teal, orange, yellow, and coffee colors appear as semantic signals rather than decoration. Information architecture is task-first: resume work, find a capability, understand its authority and access, act, and inspect the result.

Every operational statement must come from a live contract. Static examples must be identified as previews or demonstration data. Organizational context, provenance, version, permission, and state remain visible whenever they affect a decision.

**Key Characteristics:**

- Warm off-white canvas with crisp white surfaces and restrained one-pixel separators.
- Deep teal for structure and primary action; official KYA teal for health, focus, and active relationships.
- Orange for governed action or review, yellow for attention, and coffee for restriction or provenance.
- Task-first employee experience, governed creation Studio, and distinct administration control plane.
- Tables, trees, timelines, and split views when relationships matter; cards only for truly independent choices.
- Relevant energy and collaboration photography on authentication or onboarding surfaces only.
- Exact product spelling: **KYA-Platform**.

## Colors

### Brand & Accent

- **KYA Teal** (`{colors.kya-teal}` — #1ca18c): Official brand color. Used for focus, healthy state, active relationships, and compact icon surfaces.
- **KYA Orange** (`{colors.kya-orange}` — #f99d32): Governed action, review, approval, or a decision requiring human attention. It is not a general background color.
- **KYA Yellow** (`{colors.kya-yellow}` — #e8e748): Non-blocking attention and pending verification. Always paired with a text label.
- **KYA Coffee** (`{colors.kya-coffee}` — #875028): Restriction, provenance, institutional context, or protected access.
- **Deep Teal** (`{colors.deep-teal}` — #063d3a): Product structure, navigation, headings, and primary actions. It is the main digital extension of the KYA palette.

### Surface

- **Warm Ground** (`{colors.warm-ground}` — #f7f6f1): Default application canvas.
- **Surface** (`{colors.surface}` — #ffffff): Main work surface, panels, forms, menus, and tables.
- **Surface Subtle** (`{colors.surface-subtle}` — #f8faf9): Hovered rows, secondary work zones, and quiet grouping.
- **Teal Wash** (`{colors.teal-wash}` — #e8f5f2): Active navigation, selected items, and healthy summaries.
- **Orange Wash** (`{colors.orange-wash}` — #fff7ed): Review and decision context.
- **Yellow Wash** (`{colors.yellow-wash}` — #fbfadf): Non-blocking caution context.
- **Coffee Wash** (`{colors.coffee-wash}` — #f8f2ed): Restricted or provenance context.

### Hairlines & Borders

- **Circuit Line** (`{colors.circuit-line}` — #d9e2df): Default one-pixel separator and panel border.
- **Circuit Line Strong** (`{colors.circuit-line-strong}` — #b9c8c3): Selected table rows, structural boundaries, and high-density controls.
- **Focus Ring** (`{colors.focus-ring}` — rgba(28, 161, 140, 0.24)): Three-pixel keyboard focus halo.

### Text

- **Control Ink** (`{colors.control-ink}` — #14221f): Primary text and operational facts.
- **Muted Ink** (`{colors.muted-ink}` — #5f6d69): Supporting text, metadata, and explanations.
- **On Deep** (`{colors.on-deep}` — #ffffff): Text on deep-teal surfaces or image overlays.
- **On Deep Muted** (`{colors.on-deep-muted}` — #d5e9e5): Supporting text on deep surfaces.

### Semantic

- **Healthy** (`{colors.healthy}` — #1ca18c): Available, verified, connected, or operational.
- **Review** (`{colors.review}` — #de6c00): Human review, approval, or consequential action required.
- **Warning** (`{colors.warning}` — #777600): Attention without immediate failure.
- **Restricted** (`{colors.restricted}` — #875028): Permission-limited, protected, or confidential.
- **Neutral** (`{colors.neutral}` — #7b8783): Informational, inactive, inherited, or not yet evaluated.
- **Critical** (`{colors.critical}` — #a43b32): Failed, revoked, or blocked. Reserved for actual failures.

Color never communicates state alone. A status combines a dot or icon, a label, and enough context to explain the consequence.

## Typography

### Font Family

KYA-Platform uses **Segoe UI Variable** when available, followed by Segoe UI, Aptos, and `sans-serif`. This system stack is fast, readable, and available across the current Windows-centered environment. No typeface is described as official unless KYA supplies and licenses it.

The voice is institutional and direct. Headings are compact and confident; body text is calm and explanatory. Uppercase is limited to short eyebrow labels and table metadata.

### Hierarchy

| Token | Size | Weight | Line Height | Letter Spacing | Use |
|---|---:|---:|---:|---:|---|
| `{typography.display-lg}` | clamp(34px, 4vw, 52px) | 760 | 1.04 | -0.04em | Authentication and exceptional first-run statements |
| `{typography.display-md}` | clamp(30px, 3vw, 44px) | 750 | 1.08 | -0.04em | Primary screen title |
| `{typography.display-sm}` | 30px | 740 | 1.12 | -0.03em | Studio document or detailed entity title |
| `{typography.heading-lg}` | 24px | 730 | 1.2 | -0.025em | Major section title |
| `{typography.heading-md}` | 19px | 720 | 1.25 | -0.02em | Panel heading |
| `{typography.heading-sm}` | 16px | 700 | 1.3 | 0 | Dense panel and rail heading |
| `{typography.body-lg}` | 17px | 400 | 1.55 | 0 | Lead paragraph |
| `{typography.body-md}` | 14px | 400 | 1.55 | 0 | Default body and controls |
| `{typography.body-sm}` | 13px | 400 | 1.5 | 0 | Supporting explanations |
| `{typography.meta}` | 12px | 600 | 1.4 | 0 | Metadata, table cells, and status text |
| `{typography.caption}` | 11px | 600 | 1.35 | 0 | Secondary identifiers and compact context |
| `{typography.eyebrow}` | 11px | 800 | 1.3 | 0.12em | Short uppercase section identifier |

### Principles

- Use no more than three visible typographic levels in one panel.
- Keep body copy at 14px or above when it carries instructions or decisions.
- Use weight and spacing before introducing another color.
- Keep labels sentence-case except short eyebrows and compact metadata headers.
- Use tabular numerals for versions, dates, health counts, and audit identifiers.

### Note on Font Substitutes

On non-Windows systems, use Aptos or the native system sans-serif. Do not load an external font only to imitate another brand. If KYA later supplies a licensed corporate typeface, introduce it through the shared token package and validate French accents, numerals, and low-bandwidth loading before rollout.

## Layout

### Spacing System

- **Base unit:** 4px.
- **Tokens:** `{spacing.xxs}` 4px · `{spacing.xs}` 8px · `{spacing.sm}` 12px · `{spacing.md}` 16px · `{spacing.lg}` 20px · `{spacing.xl}` 24px · `{spacing.xxl}` 32px · `{spacing.section}` 40px · `{spacing.hero}` 56px.
- **Control height:** 42px desktop and at least 44px on touch layouts.
- **Panel padding:** 20–24px desktop; 16–18px mobile.
- **Dense rows:** 48–56px depending on metadata depth.

### Grid & Container

- **Desktop shell:** 224px fixed sidebar and 68px contextual top bar.
- **Collapsed shell:** 82px icon sidebar between 761px and 1100px.
- **Content width:** up to 1560px centered within the remaining canvas.
- **Task-first home:** two columns, approximately 56/44.
- **Catalogue:** filters, results, and detail in a split-view arrangement.
- **Studio and administration:** three panes where hierarchy, work surface, and policy context must coexist.
- **Mobile:** stacked work surface with a horizontally scrollable bottom navigation rail.

### Whitespace Philosophy

Whitespace separates responsibilities rather than decorating the screen. Primary tasks receive breathing room; operational lists remain compact. A surface should not gain another nested card when a divider, heading, or row is sufficient. Long data structures scroll inside their work area rather than forcing the entire page sideways.

## Elevation & Depth

| Level | Treatment | Use |
|---|---|---|
| Flat | White or subtle surface with 1px border | Panels, tables, lists, forms |
| Selected | Teal wash or inset 3px teal accent | Current navigation, selected row, active context |
| Raised | `0 18px 44px rgba(6, 61, 58, 0.09)` | Menus and temporary overlays |
| Floating | `0 18px 44px rgba(6, 61, 58, 0.25)` | Toasts and consequential transient feedback |
| Photographic | Full-bleed image with deep-teal readability overlay | Authentication and onboarding only |

The application does not use drop shadows on every card. Depth comes primarily from grouping, border contrast, and selected state. Image overlays must preserve the subject while guaranteeing readable white text.

### Decorative Depth

There is no decorative circuit motif in authentication. A restrained inset brand line may identify a selected or highlighted operational surface, but it must not become a repeated card decoration. Photography supplies emotional depth; tables, trees, and timelines supply structural depth.

## Shapes

### Border Radius Scale

| Token | Value | Use |
|---|---:|---|
| `{rounded.xs}` | 4px | Keyboard hints and tiny technical labels |
| `{rounded.sm}` | 7px | Buttons, inputs, navigation rows, icon tiles |
| `{rounded.md}` | 10px | Panels, menus, and work surfaces |
| `{rounded.lg}` | 14px | Rare onboarding or authentication containers |
| `{rounded.full}` | 9999px / 50% | Status dots, people, steps, and counts only |

Rounded rectangles are functional and restrained. Do not turn buttons, tabs, filters, or containers into pills by default. Circles are reserved for people, state, numeric counts, or sequential steps.

### Photography Geometry

Authentication photography is full-bleed with no ornamental frame. Solar infrastructure, field work, technical collaboration, and controlled AI authorization are the preferred subjects. Crop around the human task, preserve useful negative space for text, and avoid embedded text, invented uniforms, fake interfaces, or visible third-party logos.

## Components

### Application Shell

**`app-shell`** — Fixed role-aware sidebar, contextual top bar, and scrollable content canvas. The shell shows the exact `KYA-Platform` name, active workspace, global search, notifications, and account access. Administrative destinations are rendered only when authorization permits them.

**`context-switcher`** — Shows active organizational and workspace scope. Changing context recalculates effective rights; it does not merely filter the screen.

**`global-search`** — Searches capabilities and actions. Desktop shortcut is Ctrl/Cmd+K. Search results must remain permission-filtered.

### Navigation

**`primary-nav-item`** — 44px row with authored SVG icon and sentence-case label. Active state uses teal wash plus a 3px inset teal marker.

**`mobile-nav-rail`** — Bottom navigation with 44px minimum targets. It may scroll horizontally when employee, Studio, and administration destinations cannot fit without truncation.

### Buttons

**`button-primary`** — Deep teal fill, white label, 7px radius, 44px minimum height. Use for the principal available action.

**`button-review`** — Orange emphasis for a real human review, approval, or consequential decision. It must not substitute for the standard primary button.

**`button-secondary`** — White surface, circuit-line border, deep-teal text. Use for reversible secondary actions.

**`button-icon`** — 40px desktop or 44px touch target with an authored SVG icon and accessible name.

Disabled buttons retain readable labels and explain the missing dependency in visible nearby copy or a `title` attribute.

### Status & Feedback

**`status-label`** — Compact dot + text combination. It uses semantic colors and never relies on color alone.

**`toast`** — Floating deep-teal confirmation for local, reversible feedback. Failures use a persistent inline error rather than a disappearing toast.

**`empty-state`** — States what is absent, why it may be absent, and the next permitted action. Permission-filtered emptiness must not imply that the underlying resource does not exist.

### Cards & Containers

**`surface`** — Flat white panel with one-pixel border and 10px radius. Use only when content shares one responsibility.

**`action-row`** — Full-width row for an application, Skill, MCP, person, system, or decision. Preferred over a card when several comparable records form a set.

**`split-view`** — Filter/list/detail composition for the governed catalogue and record administration.

**`policy-rail`** — Narrow explanatory rail for permissions, authority boundaries, lifecycle, or security context.

### Data & Administration

**`organization-tree`** — Group, country, agency, direction, unit, and other configured nodes with temporal validity. It does not encode access roles directly.

**`assignment-timeline`** — Shows previous, current, and scheduled assignments without rewriting history.

**`core-record-list`** — Reads authoritative KYA Core entities such as organizational units, parties, clients, and projects with source, version, and state.

**`authority-boundary`** — Explains which system is authoritative for each domain and how adapters communicate with it.

### Studio

**`artifact-tree`** — Displays the package structure of a Skill or MCP, including `SKILL.md`, agent metadata, references, scripts, assets, tests, and manifest when applicable.

**`artifact-editor`** — Provides preview, diff, and validation views. It never represents a local edit as published.

**`publication-lifecycle`** — Draft → deterministic checks → business/technical review → approval → immutable publication. Each transition is permission-checked, idempotent, and audited.

### MCP & AI Environments

**`ai-connection-list`** — Lists authorized Claude, ChatGPT, Codex, or other supported clients without storing their private credentials in the browser.

**`effective-tool-profile`** — Reads the real profile calculated from identity, active unit, OAuth client, grant scopes, role policies, and personal restrictive preferences.

**`tool-preference-row`** — Allows a user to disable an inherited tool or return to inheritance. Users cannot enable a tool that policy has not granted.

### Inputs & Forms

**`text-input`** — White surface, one-pixel circuit border, 7px radius, and 46px preferred height. Focus uses the shared teal ring.

**`auth-form`** — Plain and fast. Sign-in and registration may change the approved background image while the form structure remains stable.

**`oauth-consent`** — Names the requesting client, requested scopes, active organizational context, and revocation boundary before approval.

### Brand Media

**`official-logo`** — Use the supplied KYA-Energy Group logo asset. Do not redraw, recolor, distort, or replace it with an invented mark. Product UI may use a compact KYA-Platform wordmark only when the official group logo remains available in the brand system.

## Do's and Don'ts

### Do

- Spell the product name `KYA-Platform` everywhere.
- Use the supplied KYA-Energy Group logo media without alteration.
- Show active unit, workspace, role basis, version, provenance, and state when they affect an action.
- Use live API contracts for operational claims and explicit preview labels for unconnected work.
- Separate employee use, governed creation, and platform administration.
- Prefer a list, table, tree, timeline, or split view when it explains relationships better than cards.
- Keep AI responsible for reasoning and governed software responsible for deterministic execution.
- Provide loading, empty, error, restricted, conflict, and success states.
- Preserve keyboard operation, visible focus, French accents, and reduced-motion behavior.

### Don't

- Don't invent metrics, approvals, permissions, customers, production health, or installed versions.
- Don't expose an administrative destination solely because frontend code exists for it.
- Don't duplicate authoritative records between KYA Core and business applications.
- Don't store enterprise secrets in frontend state, logs, manifests, or Skill assets.
- Don't use decorative circuits on authentication pages.
- Don't use orange, yellow, or coffee as general decoration.
- Don't create a dashboard of interchangeable rounded cards when a task or relationship should lead the page.
- Don't let a user enable an MCP tool that policy has not granted.

## Responsive Behavior

### Breakpoints

| Token | Width | Behavior |
|---|---:|---|
| `{breakpoints.wide}` | ≥ 1440px | Full 224px sidebar and three-pane work surfaces |
| `{breakpoints.desktop}` | 1101–1439px | Full sidebar; narrower detail and policy rails |
| `{breakpoints.compact}` | 761–1100px | 82px icon sidebar; secondary rails stack below the main work surface |
| `{breakpoints.mobile}` | ≤ 760px | Bottom navigation, stacked content, full-width primary actions |

### Touch Targets

All touch actions are at least 44 × 44px. Dense desktop tables may use 40–42px controls only when a separate mobile rule restores the 44px target. Icon-only controls always have accessible names.

### Collapsing Strategy

- The active context remains visible before optional account metadata.
- Global search occupies its own row on mobile.
- Studio file tree and policy rail stack around the editor without hiding lifecycle state.
- Catalogue filters become a scrollable or disclosed control; record detail follows results.
- Administration lists stay readable and do not compress status text into icons alone.
- The mobile navigation rail scrolls horizontally rather than removing Studio or administration access.

### Image Behavior

Authentication images use `object-fit: cover`, retain the human or technical subject, and may shift crop by breakpoint. Registration, sign-in, and AI authorization may use distinct approved images. Working application screens do not download large decorative images.

## Iteration Guide

1. Start with the user's task and the system-of-record boundary, not with a dashboard layout.
2. Identify the active identity, organizational context, permissions, data source, and lifecycle state.
3. Choose the smallest relationship-aware pattern: row, table, tree, timeline, split view, or focused surface.
4. Apply shared tokens and components from `@kya/design-system`; do not redeclare brand values in feature code.
5. Connect read operations before write operations. Label any temporary reference data.
6. For writes, implement permission checks, validation, idempotency, optimistic-conflict handling, audit, and clear recovery.
7. Validate desktop and mobile layouts, keyboard use, contrast, loading, empty, error, restricted, and reduced-motion states.
8. Update this document, its machine-readable sidecar, the Design System Skill, and visual regression references when an approved system rule changes.

## Known Gaps

- The current compact product mark is code-rendered; the official KYA-Energy Group logo is stored as media and still needs a dedicated responsive logo component for all shell contexts.
- Studio read-only structure is implemented, but artifact creation, deterministic validation, review, publication, installation, and rollback still need end-to-end API wiring.
- Effective MCP profiles are readable, but user tool disable/inherit controls still need UI wiring and conflict handling.
- KYA Core organization, clients, and projects are readable; governed create/edit flows and historized assignments are not yet complete in the web application.
- Catalogue reference content is partially demonstrative until a permission-filtered HTTP catalogue query is exposed.
- Authenticated end-to-end tests against `kya-platform.vttlife.com` remain to be added.
- The local workstation currently runs Node 22 while the repository requires Node 24.
