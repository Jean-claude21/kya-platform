import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../platform/api', () => ({ platformRequest: vi.fn() }));

import { CatalogWorkbenchView } from './catalog-workbench';

const artifact = {
  artifact_id: 'kya:skill:kya-design-system',
  artifact_type: 'skill' as const,
  name: 'KYA Design System',
  summary: 'Design system officiel du Groupe.',
  latest_version: '1.0.0',
  lifecycle: 'published',
  owner_workspace_id: 'workspace-cvsi',
};
const detail = {
  ...artifact,
  versions: ['1.0.0', '0.9.0'],
  installable: true,
  risk: 'read',
  source_repository: 'https://github.com/kya-energy/kya-platform',
  content_digest: 'a'.repeat(64),
};

const handlers = {
  onQueryChange: () => undefined,
  onRetry: () => undefined,
  onSelect: () => undefined,
  onTypeChange: () => undefined,
};

describe('catalog workbench', () => {
  it('explains rights filtering and version safety', () => {
    const html = renderToStaticMarkup(
      <CatalogWorkbenchView
        {...handlers}
        activeType="all"
        activeUnit="direction-cvsi"
        artifacts={[artifact]}
        detail={detail}
        detailState="ready"
        error=""
        hasMore={false}
        query=""
        selectedId={artifact.artifact_id}
        state="ready"
      />,
    );

    expect(html).toContain('Filtré par droits');
    expect(html).toContain('direction-cvsi');
    expect(html).toContain('kya:skill:kya-design-system');
    expect(html).not.toContain('données de démonstration');
  });

  it('offers a governed installation plan instead of a fake write', () => {
    const html = renderToStaticMarkup(
      <CatalogWorkbenchView
        {...handlers}
        activeType="all"
        activeUnit="direction-cvsi"
        artifacts={[artifact]}
        detail={detail}
        detailState="ready"
        error=""
        hasMore={false}
        query=""
        selectedId={artifact.artifact_id}
        state="ready"
      />,
    );

    expect(html).toContain('Installer (paquet portable)');
    expect(html).toContain('Demander un plan d’installation gouverné');
    expect(html).not.toContain('disabled');
  });

  it('disables installation when the artifact has no installable release', () => {
    const html = renderToStaticMarkup(
      <CatalogWorkbenchView
        {...handlers}
        activeType="all"
        activeUnit="direction-cvsi"
        artifacts={[artifact]}
        detail={{ ...detail, installable: false }}
        detailState="ready"
        error=""
        hasMore={false}
        query=""
        selectedId={artifact.artifact_id}
        state="ready"
      />,
    );

    expect(html).toContain('Installation indisponible');
    expect(html.match(/disabled/g)?.length).toBe(1);
  });

  it('shows the deterministic plan for review before any download starts', () => {
    const plan = {
      schema_version: '1' as const,
      plan_id: 'plan-0001',
      release_id: 'release-0001',
      artifact_id: artifact.artifact_id,
      artifact_type: 'skill' as const,
      artifact_slug: 'kya-design-system',
      version: '1.0.0',
      profile: 'portable-zip' as const,
      scope: 'personal' as const,
      target: 'workspace:workspace-cvsi',
      destination: '\${USER_SELECTED_DIRECTORY}/kya-design-system-1.0.0.zip',
      package_locator: 'https://github.com/kya-energy/kya-platform/releases/download/x/x.zip',
      content_digest: 'a'.repeat(64),
      compatibility_requirement: '>=1.0.0',
      client_version: '0.0.1',
      file_count: 3,
      package_size: 1024,
      steps: [
        {
          order: 1,
          action: 'fetch-package',
          source: null,
          destination: null,
          expected_digest: null,
        },
        {
          order: 2,
          action: 'verify-content-digest',
          source: null,
          destination: null,
          expected_digest: 'a'.repeat(64),
        },
      ],
      requires_client_confirmation: true as const,
      server_writes_local_files: false as const,
    };
    const html = renderToStaticMarkup(
      <CatalogWorkbenchView
        {...handlers}
        activeType="all"
        activeUnit="direction-cvsi"
        artifacts={[artifact]}
        detail={detail}
        detailState="ready"
        error=""
        hasMore={false}
        installFlow={{ phase: 'reviewing', plan }}
        query=""
        selectedId={artifact.artifact_id}
        state="ready"
      />,
    );

    expect(html).toContain('Plan d’installation à valider');
    expect(html).toContain('Confirmer et télécharger');
    expect(html).toContain('Récupération du paquet');
    expect(html).not.toContain('Installer (paquet portable)');
  });

  it('renders truthful empty and error states', () => {
    const empty = renderToStaticMarkup(
      <CatalogWorkbenchView
        {...handlers}
        activeType="all"
        activeUnit="group"
        artifacts={[]}
        error=""
        hasMore={false}
        query=""
        selectedId=""
        state="ready"
      />,
    );
    const error = renderToStaticMarkup(
      <CatalogWorkbenchView
        {...handlers}
        activeType="all"
        activeUnit="group"
        artifacts={[]}
        error="Service inaccessible"
        hasMore={false}
        query=""
        selectedId=""
        state="error"
      />,
    );

    expect(empty).toContain('Aucune capacité visible');
    expect(error).toContain('Service inaccessible');
    expect(error).toContain('Réessayer');
  });
});
