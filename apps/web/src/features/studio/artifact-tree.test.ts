import { describe, expect, it } from 'vitest';

import { buildArtifactTree, collectFolderPaths } from './artifact-tree';

const file = (path: string) => ({ path, kind: 'text', size: 12, contentBase64: '' });

describe('artifact tree', () => {
  it('groups package files into a stable folder-first hierarchy', () => {
    const tree = buildArtifactTree([
      file('SKILL.md'),
      file('references/terminology.md'),
      file('assets/logos/kya.png'),
      file('references/architecture.md'),
      file('assets/tokens.css'),
    ]);

    expect(tree.map((node) => `${node.kind}:${node.name}`)).toEqual([
      'folder:assets',
      'folder:references',
      'file:SKILL.md',
    ]);
    expect(collectFolderPaths(tree)).toEqual(['assets', 'assets/logos', 'references']);
  });

  it('keeps the complete path on each selectable file', () => {
    const tree = buildArtifactTree([file('agents/openai.yaml')]);
    const folder = tree[0];
    expect(folder?.kind).toBe('folder');
    if (folder?.kind !== 'folder') return;
    expect(folder.children[0]).toMatchObject({
      kind: 'file',
      name: 'openai.yaml',
      path: 'agents/openai.yaml',
    });
  });
});
