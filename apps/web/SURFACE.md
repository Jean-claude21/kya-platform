# Surface brief — KYA-Platform control plane

## Scope and mode

Mode: Operate. This iteration implements the CVSI home and shared navigation shell. KYA-Platform is the central registry, governance and distribution interface. Business applications and external AI clients consume its governed capabilities.

## Reference and implementation

The latest reference is `prototypes/kya-command/index.html`, its `styles.css`, and its inherited `prototypes/kya-precision/styles.css`. Earlier circuit, network and instrument prototypes are historical explorations, not implementation references.

The React implementation is `src/screens/platform-shell.tsx` and `src/features/home/personal-home.tsx`. `src/styles/control-plane.css` owns the current shell refinements and is loaded after the legacy workbench stylesheet. Avoid applying legacy page-padding selectors to `.cvsi-home`.

## User task

Confirm the active entity, unit and role; inspect foundation domains; open a decision; reach a governed capability or its administration screen. The entity selector remains visible on every viewport. Its local selection updates the header, home context and sidebar role together.

## Visual contract

- Deep-teal navigation rail, white work surface, fine separators and restrained geometric controls.
- Official supplied KYA-Energy Group logo and exact product name `KYA-Platform`.
- Three navigation groups: personal workspace, capabilities, foundation administration.
- 224px desktop rail and 76px topbar. Content has 32px side padding, reduced to 18px on mobile.
- Six foundation domains appear as linked operational rows, with decisions alongside on wide screens.
- Orange identifies review actions; yellow indicates attention; teal indicates active or healthy states; coffee identifies restricted access.
- At narrower widths decisions stack below the foundation. Status labels remain visible in mobile rows.
- Page scrolling is vertical. Only the compact navigation strip scrolls horizontally.

## Product truth and remaining work

Home records, health and decisions are illustrative and explicitly labeled. Navigation opens existing application screens. Context selection is local preview state; this pass does not implement backend authorization, real notifications or account-menu actions. Production claims must be supplied by permission-filtered APIs before removing the preview notice.

This pass changes the home and shell only. Approval of the visual result precedes propagating these refinements to the design-system Skill and remaining workbenches.

## Verification

Reviewed in the browser at 1600px, the native narrow panel, and 390px. No document-level horizontal overflow. Entity changes propagate to the displayed context. TypeScript and production build pass. Static design checks report no findings for the changed home, shell and dedicated stylesheet.
