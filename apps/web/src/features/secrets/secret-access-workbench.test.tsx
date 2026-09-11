import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../platform/api', () => ({ platformRequest: vi.fn() }));

import { SecretAccessWorkbenchView, type SecretReferenceSummary } from './secret-access-workbench';

const reference: SecretReferenceSummary = {
  id: '019a1000-0000-7000-8000-000000000001',
  kind: 'service',
  provider: 'infisical',
  locator: 'kya/preview/DOKPLOY_TOKEN',
  key_name: 'DOKPLOY_TOKEN',
  owner_scope: 'workspace:platform',
  purpose: 'Déployer une preview',
  environment: 'preview',
  status: 'active',
  created_at: '2026-09-04T00:00:00Z',
  rotated_at: null,
  expires_at: null,
};

describe('secret access workbench', () => {
  it('explains the non-reveal boundary and scoped use', () => {
    const html = renderToStaticMarkup(
      <SecretAccessWorkbenchView
        error=""
        references={[reference]}
        selectedId={reference.id}
        state="ready"
        onSelect={() => undefined}
      />,
    );

    expect(html).toContain('sans révéler les clés');
    expect(html).toContain('La clé ne peut pas être révélée');
    expect(html).toContain('workspace:platform');
    expect(html).toContain('Révoquer en urgence · bientôt');
    expect(html).toContain('disabled');
  });

  it('renders truthful loading, error and empty states', () => {
    const loading = renderToStaticMarkup(
      <SecretAccessWorkbenchView
        error=""
        references={[]}
        selectedId=""
        state="loading"
        onSelect={() => undefined}
      />,
    );
    const failed = renderToStaticMarkup(
      <SecretAccessWorkbenchView
        error="Service inaccessible"
        references={[]}
        selectedId=""
        state="error"
        onSelect={() => undefined}
      />,
    );
    const empty = renderToStaticMarkup(
      <SecretAccessWorkbenchView
        error=""
        references={[]}
        selectedId=""
        state="ready"
        onSelect={() => undefined}
      />,
    );

    expect(loading).toContain('Lecture des références…');
    expect(failed).toContain('Service inaccessible');
    expect(empty).toContain('Aucune référence visible');
  });

  it('never renders a secret value', () => {
    const html = renderToStaticMarkup(
      <SecretAccessWorkbenchView
        error=""
        references={[reference]}
        selectedId={reference.id}
        state="ready"
        onSelect={() => undefined}
      />,
    );

    expect(html).not.toMatch(/value/i);
  });
});
