---
name: KYA Essential Prototype
description: Visual system observed in the approved personal capability workspace prototype.
colors:
  ink: "#172d28"
  muted: "#677580"
  line: "#e0e6e4"
  teal: "#1ca18c"
  deep: "#095449"
  navigation: "#f1f5f2"
  surface: "#ffffff"
  resource-selected: "#eff6f2"
  navigation-selected: "#e0efe9"
  orange: "#f99d32"
  attention-surface: "#fff5e8"
typography:
  heading:
    fontFamily: "Inter, Arial, sans-serif"
    fontSize: "36px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  section:
    fontFamily: "Inter, Arial, sans-serif"
    fontSize: "19px"
    fontWeight: 650
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Inter, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  navigation: "4px"
  button: "5px"
  control: "6px"
components:
  button-primary:
    backgroundColor: "{colors.deep}"
    textColor: "{colors.surface}"
    rounded: "{rounded.button}"
    padding: "11px 15px"
  search:
    textColor: "{colors.muted}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
---

# KYA Essential Prototype Design

## Overview

This document describes only `apps/web/prototypes/kya-essential`. It records the HTML/CSS interpretation of the third approved design image; it does not replace the production application's design system or authorize integration.

The observed visual character is a quiet personal workspace: a white work surface, pale mineral navigation, deep green actions, fine separators, and restrained amber attention cues. Capability names, active organization context, and the selected resource carry the hierarchy. The central registry is operated here; AI clients remain external destinations.

## Colors

Deep green identifies actionable controls and primary actions. Teal marks selected resource detail and availability accents. Orange marks review attention, paired with readable text rather than acting as the only status signal.

White is the main and inspector surface. Pale navigation and selected-row surfaces establish grouping without floating containers. Ink carries primary text; muted slate carries descriptive text. Fine neutral lines divide sections and rows.

The design-system resource additionally previews four brand swatches: teal, orange, yellow (`#e8e748`), and coffee (`#875028`). These preview assets are not additional general-purpose UI status colors.

## Typography

The prototype uses a self-hosted Inter variable font with Arial and sans-serif fallbacks. Weight and size establish hierarchy; the treatment follows the approved image's compact, readable sans-serif character.

The desktop page heading is 36px, the inspector title 26px, and section headings 19px. Primary resource labels are 14px at the wide desktop breakpoint; metadata and compact actions are 13px. The body uses a 1.5 line height, and inspector descriptions use 1.65. Headings use modest negative tracking; there is no decorative display or monospace face.

At mobile widths the page heading becomes 31px and section headings 18px. Current compact labels use 11–12px. Preserve meaningful size and weight differences when adjusting density.

## Layout

The wide desktop composition has a 78px sticky context bar and three columns: a 248px navigation rail, flexible main content, and a 404px inspector. Main padding is 28px vertically and 37px horizontally. The navigation and inspector independently fit the remaining viewport height.

The main surface flows from the page heading and add action through review attention, pinned resources, a flat capability list, and external AI connections. Pinned resources and AI clients use horizontal groups with fine vertical separators. Capability rows are approximately 61px high on wide desktop.

At 1450px and 1200px the columns and gaps compact. At 1000px the inspector becomes a fixed overlay. At 760px navigation becomes a drawer, the main surface becomes one column, and the top bar expands to 152px to keep both context selectors and search visible. Mobile rows are at least 73px high; pinned resources wrap. The inspector scrolls vertically to its lower actions.

## Elevation & Depth

The resting desktop surface is flat. Tonal backgrounds and one-pixel rules provide separation. Selected navigation and resource rows use a narrow inset accent. Shadows are reserved for transient layers: the narrow-layout inspector uses `-12px 12px 40px #172d281a`, and notifications use `0 8px 24px #12342925`. A translucent scrim separates an open drawer from the underlying surface.

## Shapes

Controls have modest corners: navigation and selected rows use 4px, buttons 5px, and search, attention, and resource icons 6px. Circular shapes are confined to avatars, counts, and status dots. Icons use consistent outlined SVG geometry with rounded joins, normally a 1.7 stroke width. The KYA logo is an image asset.

## Components

- Context bar: brand, native entity and unit selectors, labelled capability search, notifications, and profile. Search supports Ctrl/Cmd K.
- Navigation: labelled icon/text actions with a pale green selected background. Administration is a separate lower entry, and the displayed role is visibly contextual.
- Attention strip: pale amber background, a dot, explicit review count, and a single review action.
- Pinned resources: compact icon/name/action groups. Organizing changes the local shortcuts only.
- Capability list: flat rows containing icon, name, type/owner, status where space permits, and a trailing action. Filter tabs support arrow keys; an empty state provides reset.
- Inspector: resource type, title, owner, optional preview, description, unit availability, versions, package contents, and actions. It can be dismissed and becomes a scrolling overlay on smaller screens.
- Buttons: outlined deep-green secondary actions and one filled deep-green primary action in the inspector. Hover uses a restrained surface change. Keyboard focus uses a visible 2px outline with 3px offset.
- AI connections: three labelled external client entries with connection state and connection actions; no embedded conversation area.
- Feedback: local simulated actions produce an announced status toast. The page footer identifies the mock data and simulated connections. Reduced-motion preference disables CSS transitions.

## Do's and Don'ts

- Do preserve the approved white, mineral, green, and restrained amber composition.
- Do keep entity and unit context available at mobile widths.
- Do retain resource names, ownership, permissions context, and version details as the information hierarchy.
- Do use native controls, explicit labels, readable status text, and visible keyboard focus.
- Do keep simulated data and actions clearly labelled during visual review.
- Don't treat this prototype document as a production integration decision.
- Don't replace flat resource rows with metric cards or introduce an embedded AI chat.
- Don't expand preview swatches into unrelated interface decoration.
- Don't hide interactive controls only by positioning them offscreen; closed drawers must also leave keyboard navigation.
