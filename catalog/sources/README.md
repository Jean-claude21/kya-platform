# Governed artifact sources

This directory contains editable source trees for real KYA artifacts. Start each artifact from its
master template in `catalog/templates`; do not edit a published release in place.

```text
sources/
├── skills/
├── mcp-servers/
├── connectors/
└── applications/
```

Create a family directory with the first real artifact. Empty placeholder directories are not kept.
Validated versions are packaged and promoted to `catalog/releases`.
