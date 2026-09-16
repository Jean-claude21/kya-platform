---
name: KYA Signature Review Prototype
description: The approved light KYA capability workspace, implemented as an isolated interactive review prototype.
colors:
  canvas: "#fcfcfa"
  white: "#fff"
  ink: "#073b36"
  body: "#314c48"
  muted: "#667378"
  line: "#dce3df"
  teal: "#1ca18c"
  green: "#07564a"
  orange: "#f99d32"
  yellow: "#e8e748"
  coffee: "#875028"
typography:
  display:
    fontFamily: "Inter, Arial, sans-serif"
    fontSize: "60px"
    fontWeight: 850
    lineHeight: 1.13
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Inter, Arial, sans-serif"
    fontSize: "34px"
    fontWeight: 850
    lineHeight: 1.13
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Inter, Arial, sans-serif"
    fontSize: "15px"
    lineHeight: 1.5
  action:
    fontFamily: "Inter, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    letterSpacing: "1.5px"
components:
  button-primary:
    backgroundColor: "{colors.green}"
    textColor: "{colors.white}"
    padding: "10px 20px"
  button-outline:
    textColor: "{colors.ink}"
    padding: "10px 20px"
---

## Overview

This document describes only `apps/web/prototypes/kya-signature`. It does not replace the production application's design system or authorize integration. The visual authority is the approved light BMW-inspired KYA mock, `exec-911ae251-4c72-4fa3-84b6-b6ebb61c202f.png`.

The workspace uses a near-white canvas, emphatic forest-colored headings, restrained official KYA accents, square controls, fine dividers, and a solar installation photograph. It is an operational interface: context selection leads into capability discovery, review, and external-client setup. The prototype retains the official KYA logo; small application symbols are illustrative substitutes. All data, connection states, downloads, and actions are demonstrations.

## Colors

The frontmatter records the CSS custom properties verbatim. Teal, orange, yellow, coffee, and white carry the official KYA palette. Forest ink supplies headings and primary text; green supplies the filled primary action and focus outline. Body and muted colors distinguish supporting copy and metadata. Canvas and line keep the main composition light and flat.

Teal marks selection and positive states. Orange marks the update state and pending count. Yellow appears in the short brand stripe and the design-system palette; coffee appears in the palette. Neutral status dots use `#9aa4ac`. Color-coded statuses also carry words.

Navigation selection and outline-button hover use `#e8f4ef`; general button hover uses `#eaf4ef`; primary-button hover uses `#063e36`. The client sun symbol uses `#d77c3e`. These are implemented supporting colors, not additional official brand colors.

## Typography

Inter is self-hosted from `assets/InterVariable.woff2`, with Arial and sans-serif fallbacks. It is the approved available substitute for the reference lettering. The font supports weights 100–900 and loads with `font-display: swap`.

Headings use uppercase, balanced wrapping, the display/headline tokens, and a clear step down to mixed-case resource titles. The hero subtitle uses 27px at weight 350; desktop resource titles use 17px at weight 650, with 14px metadata. Actions use uppercase with positive letter spacing. No separate decorative or monospaced font is used.

Responsive type scales with the layout. The hero heading becomes 53px at 1450px, 45px at 1200px, 43px at 1000px, and 36px at 760px. Mobile resource names are 12px with 11px metadata; the mobile section heading is 25px. Detail headings are 28px desktop and 26px mobile, with 14px body copy at 1.7 line-height.

## Layout

The wide layout starts with an 86px sticky header and 238px sticky left navigation. The hero is 268px high, with text at the left and a masked solar photograph at the right. The workspace uses a `1.55fr / 1fr` split between the flat capability list and the action rail. Section padding is approximately 29px; row dividers establish alignment without enclosing cards. The selected 1451–1799px composition uses 74px resource rows and 87px request rows.

The 1450px breakpoint narrows the sidebar to 208px and the 1200px breakpoint to 188px, with a 78px header. At 1000px, the action rail moves beneath the capability list and its two sections sit side by side. At 760px, the sidebar becomes a menu, the header wraps to 152px, the hero is 241px, section padding is 25px by 20px, and every working section stacks in a single column. Pinned links wrap naturally. The photo's mobile opacity is 0.35 to preserve the text.

Detail panels occupy the right edge at a maximum width of 490px and fill the viewport height; on narrow screens they occupy the full width. Their content scrolls inside the panel. The context and navigation remain conceptually separate: five primary items, with Administration in its own area.

## Elevation & Depth

The interface is flat. One-pixel dividers and whitespace distinguish regions; there are no raised cards or decorative shadows. The photograph supplies visual depth. Its linear alpha mask blends into the canvas without turning the surrounding interface into a gradient surface.

The modal backdrop uses `#123a303d`. The selected navigation item has an inset 6px teal selection marker; this is a state marker, not elevation. A toast appears above the page with a solid green background.

## Shapes

Controls, rows, section boundaries, palette swatches, and panels are square. The circular exceptions are the account avatar and status dots. The tabs remain square; the selected tab has a 3px bottom underline. Outlined buttons have a 1px teal border and a minimum height of 44px.

Icons are authored SVG paths with consistent round joins and caps. The general icon frame is 24px with a 1.5px stroke; resource symbols scale larger. The letter symbols for the design system and Frappe use a square outline.

## Components

The header contains the official logo, product name, entity and unit selectors, search, and account utilities. Search filters the visible capability list; Ctrl/Cmd K focuses it. Native selects provide the context controls. The mobile menu preserves the same destinations as the desktop navigation.

Capabilities are divider-separated rows with an icon, title, type/owner metadata, state, and explicit action. Type tabs filter the list and support Arrow keys, Home, and End. Empty results include a reset action. The Catalogue view reuses the same approved visual structure and resets search and filters.

Requests and client connections use the same flat row grammar. The full-width connection-management button is the strongest action in the right rail. Small uppercase text actions carry directional or external-link icons.

Resource and configuration details use a native modal dialog with a visible close button, Escape dismissal, focus return, and background scroll locking. MCP checkbox choices are held in memory only. Simulation actions provide status text and a toast; nothing is downloaded, connected, or persisted to a backend.

Keyboard focus uses a 2px green outline with a 4px offset; search has its own enclosing focus treatment. Disabled buttons reduce opacity to 0.55. Hover transitions use 0.15s ease-out for color and background, and reduced-motion preference removes transitions. No artificial loading or error screens are introduced for local synchronous demonstration actions.

## Do's and Don'ts

- Do preserve the approved light canvas, official KYA identity, forest typography, square controls, solar image, and flat row composition.
- Do keep Administration distinct from the five primary destinations.
- Do keep labels and interaction copy in French and identify simulated behavior clearly.
- Do preserve keyboard access, readable focus, responsive wrapping, and modal focus return.
- Do keep this documentation and implementation scoped to the isolated review prototype.
- Don't interpret the prototype's illustrative data or client state as a real integration or authorization.
- Don't substitute a new dark theme, rounded card grid, decorative shadows, or a different visual direction for the approved mock.
- Don't alter or recolor the official KYA logo.
- Don't promote these prototype-local choices into global production tokens without the subsequent integration decision.
