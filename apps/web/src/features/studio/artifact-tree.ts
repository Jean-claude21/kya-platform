export type ArtifactTreeFile = {
  path: string;
  kind: string;
  size: number;
  contentBase64: string;
};

export type ArtifactTreeNode =
  | {
      kind: 'folder';
      name: string;
      path: string;
      children: ArtifactTreeNode[];
    }
  | {
      kind: 'file';
      name: string;
      path: string;
      file: ArtifactTreeFile;
    };

type MutableFolder = {
  name: string;
  path: string;
  folders: Map<string, MutableFolder>;
  files: ArtifactTreeFile[];
};

const collator = new Intl.Collator('fr', { numeric: true, sensitivity: 'base' });

function toNode(folder: MutableFolder): ArtifactTreeNode[] {
  const folders: ArtifactTreeNode[] = [...folder.folders.values()]
    .sort((left, right) => collator.compare(left.name, right.name))
    .map((child) => ({
      kind: 'folder',
      name: child.name,
      path: child.path,
      children: toNode(child),
    }));
  const files: ArtifactTreeNode[] = [...folder.files]
    .sort((left, right) => collator.compare(fileName(left.path), fileName(right.path)))
    .map((file) => ({
      kind: 'file',
      name: fileName(file.path),
      path: file.path,
      file,
    }));
  return [...folders, ...files];
}

export function fileName(path: string): string {
  return path.split('/').filter(Boolean).at(-1) ?? path;
}

export function buildArtifactTree(files: ArtifactTreeFile[]): ArtifactTreeNode[] {
  const root: MutableFolder = { name: '', path: '', folders: new Map(), files: [] };

  for (const file of files) {
    const segments = file.path.split('/').filter((segment) => segment && segment !== '.');
    if (segments.length === 0) continue;
    let parent = root;
    for (const segment of segments.slice(0, -1)) {
      const path = parent.path ? `${parent.path}/${segment}` : segment;
      const existing = parent.folders.get(segment);
      if (existing) {
        parent = existing;
        continue;
      }
      const child: MutableFolder = { name: segment, path, folders: new Map(), files: [] };
      parent.folders.set(segment, child);
      parent = child;
    }
    parent.files.push(file);
  }

  return toNode(root);
}

export function collectFolderPaths(nodes: ArtifactTreeNode[]): string[] {
  const paths: string[] = [];
  for (const node of nodes) {
    if (node.kind !== 'folder') continue;
    paths.push(node.path, ...collectFolderPaths(node.children));
  }
  return paths;
}
