import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../platform/api', () => ({ platformRequest: vi.fn() }));

import { AuditTimelineView, type AuditEvent } from './audit-timeline';

const publishedEvent: AuditEvent = {
  id: '019a3000-0000-7000-8000-000000000001',
  occurred_at: '2026-09-05T10:18:00Z',
  actor_id: '019a3000-0000-7000-8000-000000000002',
  actor_context: {},
  action: 'Artefact publié',
  target_type: 'Skill',
  target_id: 'kya:skill:kya-design-system',
  scope: 'workspace:platform',
  environment: 'test',
  decision: 'Autorisée',
  outcome: 'Réussie',
  correlation_id: '019a3000-0000-7000-8000-000000000003',
  causation_id: null,
  metadata: {},
  protected_content: null,
};

describe('audit timeline', () => {
  it('shows scoped evidence and explains protected-content separation', () => {
    const html = renderToStaticMarkup(
      <AuditTimelineView
        contentMode="metadata_only"
        error=""
        events={[publishedEvent]}
        query=""
        state="ready"
        workspaceKey="platform"
        onQueryChange={() => undefined}
      />,
    );

    expect(html).toContain('Piste d’audit');
    expect(html).toContain('Vue métadonnées uniquement');
    expect(html).toContain('Le contenu métier reste masqué');
    expect(html).toContain('Historique de l’espace');
    expect(html).toContain('Artefact publié');
    expect(html).not.toContain('secret-value');
  });

  it('renders a truthful empty state and truthful states', () => {
    const empty = renderToStaticMarkup(
      <AuditTimelineView
        contentMode="metadata_only"
        error=""
        events={[]}
        query=""
        state="ready"
        workspaceKey="interns"
        onQueryChange={() => undefined}
      />,
    );
    const loading = renderToStaticMarkup(
      <AuditTimelineView
        contentMode="metadata_only"
        error=""
        events={[]}
        query=""
        state="loading"
        workspaceKey="platform"
        onQueryChange={() => undefined}
      />,
    );
    const failed = renderToStaticMarkup(
      <AuditTimelineView
        contentMode="metadata_only"
        error="Service inaccessible"
        events={[]}
        query=""
        state="error"
        workspaceKey="platform"
        onQueryChange={() => undefined}
      />,
    );

    expect(empty).toContain('Aucun événement autorisé');
    expect(empty).not.toContain('Artefact publié');
    expect(loading).toContain('Lecture de la piste d’audit…');
    expect(failed).toContain('Service inaccessible');
  });
});
