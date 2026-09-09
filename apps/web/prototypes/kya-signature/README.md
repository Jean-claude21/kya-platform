# KYA-Platform: light signature prototype

Run the repository's static prototype server and open `/kya-signature/index.html`.
This is an isolated HTML/CSS/JavaScript visual-review surface, not a production integration.

## Verification

From the repository root, with the static server on `127.0.0.1:4195`:

```sh
node apps/web/prototypes/kya-signature/verify.mjs
```

The check exercises filters, search, keyboard tabs, context selection, accessible dialogs,
focus restoration, mobile overflow and in-memory MCP preferences. Screenshots are saved in
`verification/`. No real credentials, downloads, client connections or authorizations are changed.

## Assets and provenance

- `assets/kya-logo.png`: existing official KYA logo, copied without modification.
- `assets/InterVariable.woff2`: existing self-hosted Inter, with `Inter-LICENSE.txt`.
- `assets/solar-panorama.png`: generated with the built-in image-generation tool; an
  illustrative scene, not a photograph of a verified KYA installation.
- Approved composition: `exec-911ae251-4c72-4fa3-84b6-b6ebb61c202f.png` from the design conversation.

Solar asset prompt: reproduce the solar photograph from the approved light UI as a standalone
3:1 photorealistic landscape; blue photovoltaic panels in ordered rows, green grass, scattered
West African trees, distant hills and bright morning sun toward the upper right; horizon in the
top quarter; full-bleed photograph with no text, UI, borders, logos or white fade. A CSS mask
implements the approved transition into the light background.

The global app and earlier prototypes remain unchanged. `DESIGN.md` documents this prototype only.
