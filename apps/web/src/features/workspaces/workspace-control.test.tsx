import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../platform/api', () => ({ platformRequest: vi.fn() }));

import { WorkspaceControl, type WorkspaceSummary } from './workspace-control';

const visibleWorkspaces: WorkspaceSummary[] = [
  {
    id: '01991c00-0000-7000-8000-000000000001',
    key: 'platform',
    name: 'KYA-Platform',
    kind: 'team',
    classification: 'internal',
  },
];

describe('workspace control', () => {
  it('renders only the workspaces already filtered for the principal', () => {
    const html = renderToStaticMarkup(
      <WorkspaceControl
        activeKey="platform"
        isOpen
        workspaces={visibleWorkspaces}
        onOpenChange={() => undefined}
        onSelect={() => undefined}
      />,
    );

    expect(html).toContain('KYA-Platform');
    expect(html).not.toContain('Direction générale');
    expect(html).toContain('Seuls les espaces autorisés par vos droits sont proposés ici.');
  });

  it('shows a truthful empty state when no workspace is authorized', () => {
    const html = renderToStaticMarkup(
      <WorkspaceControl
        activeKey=""
        isOpen
        workspaces={[]}
        onOpenChange={() => undefined}
        onSelect={() => undefined}
      />,
    );

    expect(html).toContain('Aucun espace accessible dans ce contexte.');
  });
});
