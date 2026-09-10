# KYA Precision Circuit

This document records the visual decisions implemented by the standalone HTML/CSS validation prototype. It does not replace the production application's design system until the prototype is approved.

## Direction

KYA Platform is treated as a precise digital cockpit: a governed access hub, catalog, capability factory, and progressive foundation administration surface. The interface avoids generic SaaS card grids and expresses the KYA identity through a functional circuit language.

## Shape semantics

- Circles identify capabilities, identities, active nodes, and decision points.
- Lines communicate flow, dependency, progress, or organizational connection.
- Junctions identify a choice, transformation, or governance checkpoint.
- Plug endpoints mean connect, install, publish, or deploy.
- Rectangles hold stable resources such as applications, documents, MCP servers, Skills, and datasets.

## Tokens

- Brand teal: `#1CA18C`
- Brand orange: `#F99D32`
- Brand yellow: `#E8E748`
- Brand coffee: `#875028`
- White: `#FFFFFF`
- Deep teal: `#063B37`
- Text ink: `#102321`
- Ground: `#F3F7F6`
- Divider: `#D5E1DF`
- Control radius: `4px`
- Panel radius: `6px`
- Border width: `1px`

## Typography

Headings use Arial Narrow-compatible system fonts to preserve the condensed institutional character already present in KYA's graphic material. Body copy uses Arial and Segoe UI fallbacks to avoid a runtime font dependency during validation.

## Surface rules

- Use continuous planes, rows, and hairline dividers before introducing cards.
- Reserve orange for actions that require a decision or immediate intervention.
- Reserve yellow for live focus and active circuit junctions.
- Use coffee for restricted, formal, or sensitive governance states.
- Show every status with text; color is never the only carrier of meaning.
- Keep the active organizational scope and role visible.
- Hide the foundation administration surface from unauthorized users.
- Never expose raw secrets through the browser.

## Responsive behavior

The desktop sidebar collapses to an icon rail on medium screens and becomes bottom navigation on small screens. Data rows retain their structure through horizontal scrolling. The foundation circuit becomes a scroll-snapping sequence rather than compressing labels beyond readability.
