import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../platform/api', () => ({ platformRequest: vi.fn() }));

import { SystemAuthorityWorkbenchView, type DataSourceSummary } from './system-authority-workbench';

const source: DataSourceSummary = {
  id: '019a2000-0000-7000-8000-000000000001',
  key: 'kya-platform-catalog',
  name: 'KYA-Platform',
  kind: 'api',
  owner_unit_id: '019a2000-0000-7000-8000-000000000002',
  system_artifact_id: null,
  has_credentials: false,
  status: 'active',
};

describe('system authority workbench', () => {
  it('makes ownership, authority and no-copy semantics explicit', () => {
    const html = renderToStaticMarkup(
      <SystemAuthorityWorkbenchView
        error=""
        selectedId={source.id}
        sources={[source]}
        state="ready"
        onSelect={() => undefined}
      />,
    );

    expect(html).toContain('KYA-Platform');
    expect(html).toContain('Unité propriétaire');
    expect(html).toContain('limitée aux données déclarées');
    expect(html).toContain('bloquerait la publication');
    expect(html).not.toContain('données de démonstration');
  });

  it('does not imitate a connected authority mutation', () => {
    const html = renderToStaticMarkup(
      <SystemAuthorityWorkbenchView
        error=""
        selectedId={source.id}
        sources={[source]}
        state="ready"
        onSelect={() => undefined}
      />,
    );

    expect(html).toContain('Ajouter une source · bientôt');
    expect(html).toContain('disabled');
  });

  it('renders truthful loading, error and empty states', () => {
    const loading = renderToStaticMarkup(
      <SystemAuthorityWorkbenchView
        error=""
        selectedId=""
        sources={[]}
        state="loading"
        onSelect={() => undefined}
      />,
    );
    const failed = renderToStaticMarkup(
      <SystemAuthorityWorkbenchView
        error="Service inaccessible"
        selectedId=""
        sources={[]}
        state="error"
        onSelect={() => undefined}
      />,
    );
    const empty = renderToStaticMarkup(
      <SystemAuthorityWorkbenchView
        error=""
        selectedId=""
        sources={[]}
        state="ready"
        onSelect={() => undefined}
      />,
    );

    expect(loading).toContain('Lecture des sources…');
    expect(failed).toContain('Service inaccessible');
    expect(empty).toContain('Aucune source visible');
  });
});

