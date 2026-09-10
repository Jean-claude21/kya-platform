import { renderToStaticMarkup } from 'react-dom/server';
import type { ComponentProps } from 'react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../platform/api', () => ({ platformRequest: vi.fn() }));

import { AiEnvironmentView, type ActiveConnector, type EffectiveProfile } from './ai-environment';

const connector: ActiveConnector = {
  client_id: 'generated-client-id',
  client_name: 'Claude Desktop',
  scopes: ['catalog:read', 'data:read'],
  connected_at: '2026-09-10T08:00:00Z',
  expires_at: '2026-10-10T08:00:00Z',
};

const profile: EffectiveProfile = {
  client_id: connector.client_id,
  active_unit_key: 'direction-cvsi',
  tool_keys: ['search_data_assets'],
  revision: 'a'.repeat(64),
  shadow_diverged: false,
};

function render(overrides: Partial<ComponentProps<typeof AiEnvironmentView>> = {}) {
  return renderToStaticMarkup(
    <AiEnvironmentView
      connectors={[connector]}
      connectorsState="ready"
      error=""
      profile={profile}
      profileState="ready"
      selectedConnector={connector}
      onRetry={() => undefined}
      onSelect={() => undefined}
      {...overrides}
    />,
  );
}

describe('AI environment', () => {
  it('renders the discovered client and its effective governed profile', () => {
    const html = render();

    expect(html).toContain('Claude Desktop');
    expect(html).toContain('direction-cvsi');
    expect(html).toContain('search_data_assets');
    expect(html).toContain('catalog:read, data:read');
    expect(html).not.toContain('Vérifier le profil');
  });

  it('renders a truthful empty state when the active unit has no connector', () => {
    const html = render({
      connectors: [],
      profile: null,
      profileState: 'ready',
      selectedConnector: null,
    });

    expect(html).toContain('Aucune connexion MCP active');
    expect(html).toContain('après la validation OAuth');
  });

  it('renders a recoverable service error', () => {
    const html = render({
      connectors: [],
      connectorsState: 'error',
      error: 'Le service est temporairement indisponible.',
      profile: null,
      profileState: 'error',
      selectedConnector: null,
    });

    expect(html).toContain('Profil indisponible');
    expect(html).toContain('Réessayer');
  });
});
