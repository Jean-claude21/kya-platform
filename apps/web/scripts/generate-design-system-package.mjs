import { readFileSync, writeFileSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const skillRoot = join(
  here,
  '..',
  '..',
  '..',
  'catalog',
  'templates',
  'skill',
  'kya-design-system',
);
const textFiles = [
  'SKILL.md',
  'agents/openai.yaml',
  'artifact.manifest.json',
  'references/DESIGN.md',
  'references/implementation.md',
  'assets/tokens.css',
];
const binaryFiles = ['assets/brand/kya-energy-group-logo.png'];

const entries = [];
for (const path of textFiles) {
  const content = readFileSync(join(skillRoot, path), 'utf8');
  entries.push({ path, kind: 'text', size: Buffer.byteLength(content), content });
}
for (const path of binaryFiles) {
  const size = statSync(join(skillRoot, path)).size;
  entries.push({ path, kind: 'binary', size, content: null });
}

const header =
  '// Generated from catalog/templates/skill/kya-design-system by generate-design-system-package.mjs.\n// Do not edit by hand; run `pnpm --filter @kya/web gen:design-system`.\n';
const body =
  "export type DesignSystemFile = { path: string; kind: 'text' | 'binary'; size: number; content: string | null };\n\nexport const designSystemPackage: DesignSystemFile[] = " +
  JSON.stringify(entries, null, 2) +
  ';\n';
writeFileSync(
  join(here, '..', 'src', 'features', 'studio', 'design-system-package.gen.ts'),
  header + body,
);
process.stdout.write('generated ' + entries.length + ' files\n');
