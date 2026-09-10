import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { WorkspaceAccessPanel, WorkspaceControl, type WorkspaceSummary } from './workspace-control';

const visibleWorkspaces: WorkspaceSummary[] = [
  {
    entity: 'KYA-Energy Togo',
    key: 'platform',
    name: 'KYA-Platform',
    unit: 'Direction des Systèmes',
    scope: 'CVSI · Togo',
    role: 'Gestionnaire',
    classification: 'Interne',
  },
];

describe('workspace surfaces', () => {
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
    expect(html).toContain('L’entité, l’unité et les droits sont recalculés ensemble.');
  });

  it('shows access provenance and keeps unwired mutations visibly disabled', () => {
    const html = renderToStaticMarkup(
      <WorkspaceAccessPanel
        activeKey="platform"
        workspaces={visibleWorkspaces}
        onSelect={() => undefined}
      />,
    );

    expect(html).toContain('Pourquoi vous avez accès');
    expect(html).toContain('interdiction explicite');
    expect(html).toContain('Ajouter un membre · bientôt');
    expect(html).toContain('disabled');
  });
});
