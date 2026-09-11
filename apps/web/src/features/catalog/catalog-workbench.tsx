import { useCallback, useEffect, useMemo, useState } from 'react';

import { Icon, StatusBadge } from '@kya/design-system';
import type { IconName } from '@kya/design-system';

import { idempotencyKey, platformRequest } from '../../platform/api';

export type ArtifactType = 'skill' | 'mcp' | 'app' | 'api' | 'dataset' | 'template';

export type CatalogArtifact = {
  artifact_id: string;
  artifact_type: ArtifactType;
  name: string;
  summary: string | null;
  latest_version: string;
  lifecycle: string;
  owner_workspace_id: string;
};

export type CatalogArtifactDetail = CatalogArtifact & {
  versions: string[];
  installable: boolean;
  risk: string;
  source_repository: string;
  content_digest: string;
};

type CatalogResponse = {
  items: CatalogArtifact[];
  active_unit: string;
  has_more: boolean;
};

type RequestState = 'loading' | 'ready' | 'error';

type InstallationProfile = 'codex' | 'claude-code' | 'portable-zip';
type InstallationScope = 'personal' | 'project';

type InstallationStep = {
  order: number;
  action: string;
  source: string | null;
  destination: string | null;
  expected_digest: string | null;
};

type InstallationPlan = {
  schema_version: '1';
  plan_id: string;
  release_id: string;
  artifact_id: string;
  artifact_type: ArtifactType;
  artifact_slug: string;
  version: string;
  profile: InstallationProfile;
  scope: InstallationScope;
  target: string;
  destination: string;
  package_locator: string;
  content_digest: string;
  compatibility_requirement: string;
  client_version: string;
  file_count: number;
  package_size: number;
  steps: InstallationStep[];
  requires_client_confirmation: true;
  server_writes_local_files: false;
};

type InstallFlowState =
  | { phase: 'idle' }
  | { phase: 'planning' }
  | { phase: 'reviewing'; plan: InstallationPlan }
  | { phase: 'fetching'; plan: InstallationPlan }
  | { phase: 'verifying'; plan: InstallationPlan }
  | { phase: 'installed'; plan: InstallationPlan; installationId: string }
  | { phase: 'error'; message: string };

const APP_CLIENT_VERSION = '0.0.1';
const WORKSPACE_TARGET_PREFIX = 'workspace:';

const types: Array<{ value: ArtifactType | 'all'; label: string }> = [
  { value: 'all', label: 'Toutes' },
  { value: 'skill', label: 'Skills' },
  { value: 'mcp', label: 'MCP' },
  { value: 'app', label: 'Apps' },
  { value: 'api', label: 'API' },
  { value: 'dataset', label: 'Données' },
];

const typeIcons: Record<ArtifactType, IconName> = {
  skill: 'skill',
  mcp: 'network',
  app: 'apps',
  api: 'command',
  dataset: 'database',
  template: 'catalog',
};

const stepLabels: Record<string, string> = {
  'fetch-package': 'Récupération du paquet',
  'verify-release-signature': 'Vérification de la signature',
  'verify-content-digest': 'Vérification de l’empreinte',
  'verify-client-compatibility': 'Vérification de compatibilité',
  'stage-files': 'Préparation locale',
  'activate-atomically': 'Activation',
  'write-installation-receipt': 'Écriture du reçu',
};

function lifecycleLabel(value: string): string {
  const labels: Record<string, string> = {
    published: 'Publié',
    approved: 'Approuvé',
    validating: 'En validation',
    candidate: 'Candidat',
    suspended: 'Suspendu',
    deprecated: 'Déprécié',
    retired: 'Retiré',
  };
  return labels[value] ?? value;
}

function lifecycleTone(value: string): 'healthy' | 'warning' | 'attention' | 'restricted' {
  if (value === 'published' || value === 'approved') return 'healthy';
  if (value === 'validating' || value === 'candidate') return 'attention';
  if (value === 'suspended' || value === 'retired') return 'restricted';
  return 'warning';
}

function toHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

async function digestPackage(bytes: ArrayBuffer): Promise<string> {
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  return toHex(hash);
}

function saveBytesAsFile(bytes: ArrayBuffer, filename: string): void {
  const blob = new Blob([bytes], { type: 'application/zip' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function CatalogWorkbenchView({
  activeType,
  activeUnit,
  artifacts,
  detail,
  detailState,
  error,
  hasMore,
  installFlow,
  query,
  selectedId,
  state,
  onInstallCancel,
  onInstallConfirm,
  onInstallStart,
  onQueryChange,
  onRetry,
  onSelect,
  onTypeChange,
}: {
  activeType: ArtifactType | 'all';
  activeUnit: string;
  artifacts: CatalogArtifact[];
  detail?: CatalogArtifactDetail | null;
  detailState?: RequestState;
  error: string;
  hasMore: boolean;
  installFlow?: InstallFlowState;
  query: string;
  selectedId: string;
  state: RequestState;
  onInstallCancel?: () => void;
  onInstallConfirm?: () => void;
  onInstallStart?: () => void;
  onQueryChange: (value: string) => void;
  onRetry: () => void;
  onSelect: (value: string) => void;
  onTypeChange: (value: ArtifactType | 'all') => void;
}) {
  const selectedSummary = artifacts.find((artifact) => artifact.artifact_id === selectedId) ?? null;
  const selected: CatalogArtifact | CatalogArtifactDetail | null =
    detail?.artifact_id === selectedId ? detail : selectedSummary;
  const selectedDetail = detail?.artifact_id === selectedId ? detail : null;
  const flow = installFlow ?? { phase: 'idle' as const };

  return (
    <main className="catalog-page">
      <section className="catalog-intro" aria-labelledby="catalog-title">
        <div>
          <span>Catalogue gouverné</span>
          <h1 id="catalog-title">Capacités disponibles pour votre rôle</h1>
          <p>Les résultats sont filtrés par vos droits avant toute lecture des métadonnées.</p>
        </div>
        <div className="catalog-proof">
          <Icon name="shield" />
          <span>
            <strong>Unité active</strong>
            {activeUnit || 'Calcul en cours'}
          </span>
        </div>
      </section>

      <aside className="catalog-filters" aria-labelledby="catalog-filter-title">
        <h2 id="catalog-filter-title">Explorer</h2>
        <label>
          <span className="sr-only">Rechercher dans le catalogue</span>
          <Icon name="search" />
          <input
            value={query}
            placeholder="Nom ou description…"
            onChange={(event) => {
              onQueryChange(event.target.value);
            }}
          />
        </label>
        {query.trim().length === 1 ? (
          <p className="catalog-query-hint">Saisissez au moins deux caractères.</p>
        ) : null}
        <div className="catalog-facets">
          {types.map((type) => (
            <button
              aria-pressed={activeType === type.value}
              key={type.value}
              type="button"
              onClick={() => {
                onTypeChange(type.value);
              }}
            >
              {type.label}
              <span>
                {type.value === 'all'
                  ? artifacts.length
                  : artifacts.filter((artifact) => artifact.artifact_type === type.value).length}
              </span>
            </button>
          ))}
        </div>
        <div className="catalog-access-note">
          <Icon name="governance" />
          <p>L’absence d’un résultat peut signifier qu’il n’est pas partagé avec votre unité.</p>
        </div>
      </aside>

      <section className="catalog-results" aria-labelledby="catalog-results-title">
        <header>
          <div>
            <h2 id="catalog-results-title">Résultats autorisés</h2>
            <p>
              {state === 'ready'
                ? `${String(artifacts.length)} capacité(s) visible(s)`
                : 'Lecture sécurisée en cours'}
            </p>
          </div>
          <StatusBadge tone="restricted">Filtré par droits</StatusBadge>
        </header>
        {state === 'loading' ? (
          <div className="catalog-state" role="status">
            <Icon name="activity" />
            <strong>Lecture du catalogue…</strong>
            <p>Les droits de votre unité sont évalués avant l’affichage.</p>
          </div>
        ) : state === 'error' ? (
          <div className="catalog-state" role="alert">
            <Icon name="lock" />
            <strong>Catalogue indisponible</strong>
            <p>{error}</p>
            <button type="button" onClick={onRetry}>
              Réessayer
            </button>
          </div>
        ) : artifacts.length === 0 ? (
          <div className="catalog-state">
            <Icon name="catalog" />
            <strong>Aucune capacité visible</strong>
            <p>Modifiez la recherche ou vérifiez le contexte organisationnel actif.</p>
          </div>
        ) : (
          <div className="artifact-grid">
            {artifacts.map((artifact) => (
              <button
                aria-current={artifact.artifact_id === selectedId ? 'true' : undefined}
                key={artifact.artifact_id}
                type="button"
                onClick={() => {
                  onSelect(artifact.artifact_id);
                }}
              >
                <span className="artifact-type">
                  <Icon name={typeIcons[artifact.artifact_type]} />
                  {artifact.artifact_type}
                </span>
                <strong>{artifact.name}</strong>
                <p>{artifact.summary ?? 'Aucune description publiée.'}</p>
                <span className="artifact-meta">
                  <small>Version {artifact.latest_version}</small>
                  <StatusBadge tone={lifecycleTone(artifact.lifecycle)}>
                    {lifecycleLabel(artifact.lifecycle)}
                  </StatusBadge>
                </span>
              </button>
            ))}
          </div>
        )}
        {hasMore ? (
          <p className="catalog-more">D’autres résultats peuvent être disponibles.</p>
        ) : null}
      </section>

      <aside className="artifact-detail" aria-labelledby="artifact-detail-title">
        {selected ? (
          <>
            <header>
              <span>{selected.artifact_type}</span>
              <h2 id="artifact-detail-title">{selected.name}</h2>
              <p>{selected.summary ?? 'Aucune description publiée.'}</p>
            </header>
            <dl>
              <div>
                <dt>Version publiée</dt>
                <dd>{selected.latest_version}</dd>
              </div>
              <div>
                <dt>Cycle de vie</dt>
                <dd>{lifecycleLabel(selected.lifecycle)}</dd>
              </div>
              {selectedDetail ? (
                <div>
                  <dt>Niveau de risque</dt>
                  <dd>{selectedDetail.risk}</dd>
                </div>
              ) : null}
              {selectedDetail ? (
                <div>
                  <dt>Versions connues</dt>
                  <dd>{selectedDetail.versions.join(' · ')}</dd>
                </div>
              ) : null}
              <div>
                <dt>Identifiant public</dt>
                <dd title={selected.artifact_id}>{selected.artifact_id}</dd>
              </div>
              <div>
                <dt>Espace propriétaire</dt>
                <dd title={selected.owner_workspace_id}>{selected.owner_workspace_id}</dd>
              </div>
              {selectedDetail ? (
                <div>
                  <dt>Dépôt source</dt>
                  <dd title={selectedDetail.source_repository}>
                    {selectedDetail.source_repository}
                  </dd>
                </div>
              ) : null}
              {selectedDetail ? (
                <div>
                  <dt>Empreinte</dt>
                  <dd title={selectedDetail.content_digest}>
                    {selectedDetail.content_digest.slice(0, 12)}…
                  </dd>
                </div>
              ) : null}
            </dl>
            <div className="install-state">
              <header>
                <Icon name="shield" />
                <span>
                  <strong>Métadonnées autorisées</strong>
                  <small>Lecture calculée dans l’unité active</small>
                </span>
                <StatusBadge tone={detailState === 'error' ? 'attention' : 'healthy'}>
                  {detailState === 'loading'
                    ? 'Lecture…'
                    : detailState === 'error'
                      ? 'Détail indisponible'
                      : 'Vérifié'}
                </StatusBadge>
              </header>
            </div>

            {flow.phase === 'idle' || flow.phase === 'planning' || flow.phase === 'error' ? (
              <footer>
                {flow.phase === 'error' ? (
                  <p className="install-error" role="alert">
                    {flow.message}
                  </p>
                ) : null}
                <button
                  disabled={!selectedDetail?.installable || flow.phase === 'planning'}
                  title={
                    selectedDetail && !selectedDetail.installable
                      ? 'Aucune version publiée installable'
                      : 'Demander un plan d’installation gouverné'
                  }
                  type="button"
                  onClick={onInstallStart}
                >
                  {flow.phase === 'planning'
                    ? 'Calcul du plan…'
                    : selectedDetail?.installable
                      ? 'Installer (paquet portable)'
                      : 'Installation indisponible'}
                </button>
              </footer>
            ) : null}

            {flow.phase === 'reviewing' ? (
              <div className="install-plan" role="group" aria-labelledby="install-plan-title">
                <h3 id="install-plan-title">Plan d’installation à valider</h3>
                <p>
                  Le serveur ne modifie aucun fichier local. Ce plan décrit ce que votre navigateur
                  exécutera après votre confirmation explicite.
                </p>
                <dl>
                  <div>
                    <dt>Destination</dt>
                    <dd>{flow.plan.destination}</dd>
                  </div>
                  <div>
                    <dt>Empreinte attendue</dt>
                    <dd title={flow.plan.content_digest}>
                      {flow.plan.content_digest.slice(0, 16)}…
                    </dd>
                  </div>
                  <div>
                    <dt>Compatibilité</dt>
                    <dd>{flow.plan.compatibility_requirement}</dd>
                  </div>
                </dl>
                <ol className="install-steps">
                  {flow.plan.steps.map((step) => (
                    <li key={step.order}>{stepLabels[step.action] ?? step.action}</li>
                  ))}
                </ol>
                <div className="install-actions">
                  <button type="button" onClick={onInstallCancel}>
                    Annuler
                  </button>
                  <button type="button" onClick={onInstallConfirm}>
                    Confirmer et télécharger
                  </button>
                </div>
              </div>
            ) : null}

            {flow.phase === 'fetching' || flow.phase === 'verifying' ? (
              <div className="install-progress" role="status">
                <Icon name="activity" />
                <p>
                  {flow.phase === 'fetching'
                    ? 'Récupération du paquet…'
                    : 'Vérification de l’empreinte…'}
                </p>
              </div>
            ) : null}

            {flow.phase === 'installed' ? (
              <div className="install-success" role="status">
                <Icon name="check" />
                <p>Paquet téléchargé et reçu enregistré.</p>
                <small title={flow.installationId}>
                  Installation {flow.installationId.slice(0, 8)}…
                </small>
              </div>
            ) : null}
          </>
        ) : (
          <div className="catalog-state catalog-state--detail">
            <Icon name="catalog" />
            <h2 id="artifact-detail-title">Aucune capacité sélectionnée</h2>
            <p>Les détails apparaîtront ici sans divulguer de contenu non autorisé.</p>
          </div>
        )}
      </aside>
    </main>
  );
}

export function CatalogWorkbench({
  typeFilter,
  initialQuery = '',
}: {
  typeFilter?: 'App' | 'Skill';
  initialQuery?: string;
}) {
  const initialType = typeFilter?.toLocaleLowerCase('fr') as ArtifactType | undefined;
  const [query, setQuery] = useState(initialQuery);
  const [activeType, setActiveType] = useState<ArtifactType | 'all'>(initialType ?? 'all');
  const [response, setResponse] = useState<CatalogResponse>({
    items: [],
    active_unit: '',
    has_more: false,
  });
  const [selectedId, setSelectedId] = useState('');
  const [detail, setDetail] = useState<CatalogArtifactDetail | null>(null);
  const [detailState, setDetailState] = useState<RequestState>('loading');
  const [state, setState] = useState<RequestState>('loading');
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [installFlow, setInstallFlow] = useState<InstallFlowState>({ phase: 'idle' });
  const normalizedQuery = query.trim();

  const retry = useCallback(() => {
    setReloadKey((value) => value + 1);
  }, []);
  const requestPath = useMemo(() => {
    const parameters = new URLSearchParams();
    if (normalizedQuery.length >= 2) parameters.set('query', normalizedQuery);
    if (activeType !== 'all') parameters.append('artifact_type', activeType);
    const suffix = parameters.toString();
    return `/catalog/artifacts${suffix ? `?${suffix}` : ''}`;
  }, [activeType, normalizedQuery]);

  useEffect(() => {
    if (normalizedQuery.length === 1) return;
    let isActive = true;
    const timer = window.setTimeout(() => {
      setState('loading');
      setError('');
      void platformRequest<CatalogResponse>(requestPath)
        .then((value) => {
          if (!isActive) return;
          setResponse(value);
          setSelectedId((current) =>
            value.items.some((artifact) => artifact.artifact_id === current)
              ? current
              : (value.items[0]?.artifact_id ?? ''),
          );
          setState('ready');
        })
        .catch((failure: unknown) => {
          if (!isActive) return;
          setResponse((current) => ({ ...current, items: [], has_more: false }));
          setError(failure instanceof Error ? failure.message : 'Le catalogue est indisponible.');
          setState('error');
        });
    }, 250);
    return () => {
      isActive = false;
      window.clearTimeout(timer);
    };
  }, [reloadKey, normalizedQuery.length, requestPath]);

  useEffect(() => {
    setInstallFlow({ phase: 'idle' });
    if (!selectedId) {
      setDetail(null);
      setDetailState('ready');
      return;
    }
    let isActive = true;
    setDetail(null);
    setDetailState('loading');
    void platformRequest<CatalogArtifactDetail>(
      `/catalog/artifacts/${encodeURIComponent(selectedId)}`,
    )
      .then((value) => {
        if (!isActive) return;
        setDetail(value);
        setDetailState('ready');
      })
      .catch(() => {
        if (!isActive) return;
        setDetailState('error');
      });
    return () => {
      isActive = false;
    };
  }, [reloadKey, selectedId]);

  const startInstall = useCallback(() => {
    if (!detail || !detail.installable) return;
    const workspaceId = detail.owner_workspace_id;
    setInstallFlow({ phase: 'planning' });
    void platformRequest<InstallationPlan>(
      `/catalog/artifacts/${encodeURIComponent(detail.artifact_id)}/installation-plan`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          version: detail.latest_version,
          target: `${WORKSPACE_TARGET_PREFIX}${workspaceId}`,
          profile: 'portable-zip' satisfies InstallationProfile,
          scope: 'personal' satisfies InstallationScope,
          client_version: APP_CLIENT_VERSION,
          confirmation: { confirmed: true },
        }),
      },
    )
      .then((plan) => {
        setInstallFlow({ phase: 'reviewing', plan });
      })
      .catch((failure: unknown) => {
        setInstallFlow({
          phase: 'error',
          message:
            failure instanceof Error
              ? failure.message
              : 'Le plan d’installation ne peut pas être calculé.',
        });
      });
  }, [detail]);

  const cancelInstall = useCallback(() => {
    setInstallFlow({ phase: 'idle' });
  }, []);

  const confirmInstall = useCallback(() => {
    setInstallFlow((current) => {
      if (current.phase !== 'reviewing') return current;
      const plan = current.plan;
      void (async () => {
        setInstallFlow({ phase: 'fetching', plan });
        try {
          const packageResponse = await fetch(plan.package_locator);
          if (!packageResponse.ok) {
            throw new Error('Le paquet publié est momentanément inaccessible.');
          }
          const bytes = await packageResponse.arrayBuffer();
          setInstallFlow({ phase: 'verifying', plan });
          const digest = await digestPackage(bytes);
          if (digest !== plan.content_digest) {
            throw new Error('L’empreinte du paquet téléchargé ne correspond pas au plan signé.');
          }
          saveBytesAsFile(bytes, `${plan.artifact_slug}-${plan.version}.zip`);
          const receipt = await platformRequest<{ installation_id: string; operation_id: string }>(
            '/catalog/installation-receipts',
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                plan_id: plan.plan_id,
                release_id: plan.release_id,
                target: plan.target,
                profile: plan.profile,
                scope: plan.scope,
                client_version: plan.client_version,
                installed_digest: digest,
                idempotency_key: idempotencyKey('installation-receipt'),
                confirmation: { confirmed: true },
              }),
            },
          );
          setInstallFlow({ phase: 'installed', plan, installationId: receipt.installation_id });
        } catch (failure) {
          setInstallFlow({
            phase: 'error',
            message:
              failure instanceof Error
                ? failure.message
                : 'L’installation n’a pas pu être confirmée en toute sécurité.',
          });
        }
      })();
      return { phase: 'fetching', plan };
    });
  }, []);

  return (
    <CatalogWorkbenchView
      activeType={activeType}
      activeUnit={response.active_unit}
      artifacts={response.items}
      detail={detail}
      detailState={detailState}
      error={error}
      hasMore={response.has_more}
      installFlow={installFlow}
      query={query}
      selectedId={selectedId}
      state={state}
      onInstallCancel={cancelInstall}
      onInstallConfirm={confirmInstall}
      onInstallStart={startInstall}
      onQueryChange={setQuery}
      onRetry={retry}
      onSelect={setSelectedId}
      onTypeChange={setActiveType}
    />
  );
}
