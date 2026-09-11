import { useEffect, useState } from 'react';

import { Icon, StatusBadge } from '@kya/design-system';

import { platformRequest } from '../../platform/api';

type SourceKind = 'web' | 'api' | 'database' | 'file' | 'stream' | 'manual';
type SourceStatus = 'draft' | 'active' | 'paused' | 'deprecated' | 'retired';

export type DataSourceSummary = {
  id: string;
  key: string;
  name: string;
  kind: SourceKind;
  owner_unit_id: string;
  system_artifact_id: string | null;
  has_credentials: boolean;
  status: SourceStatus;
};

type RequestState = 'loading' | 'ready' | 'error';

const kindLabels: Record<SourceKind, string> = {
  web: 'Web',
  api: 'API',
  database: 'Base de données',
  file: 'Fichier',
  stream: 'Flux',
  manual: 'Saisie manuelle',
};

const statusLabels: Record<SourceStatus, string> = {
  draft: 'Brouillon',
  active: 'Active',
  paused: 'En pause',
  deprecated: 'Dépréciée',
  retired: 'Retirée',
};

const statusTone: Record<SourceStatus, 'healthy' | 'attention' | 'restricted' | 'neutral'> = {
  draft: 'neutral',
  active: 'healthy',
  paused: 'attention',
  deprecated: 'attention',
  retired: 'restricted',
};

export function SystemAuthorityWorkbenchView({
  error,
  selectedId,
  sources,
  state,
  onSelect,
}: {
  error: string;
  selectedId: string;
  sources: DataSourceSummary[];
  state: RequestState;
  onSelect: (id: string) => void;
}) {
  const selected = sources.find((source) => source.id === selectedId) ?? null;

  return (
    <main className="systems-page">
      <section className="systems-intro" aria-labelledby="systems-title">
        <div>
          <h1 id="systems-title">Où se trouve la donnée qui fait foi ?</h1>
          <p>
            Chaque source enregistrée déclare son propriétaire, son type et son état. Une source
            partagée avec un autre système reste identifiable ici.
          </p>
        </div>
        <StatusBadge tone="restricted">Filtré par droits</StatusBadge>
      </section>

      <aside className="system-list" aria-labelledby="system-list-title">
        <header>
          <h2 id="system-list-title">Sources enregistrées</h2>
          <span>{sources.length}</span>
        </header>
        {state === 'loading' ? (
          <div className="catalog-state" role="status">
            <Icon name="activity" />
            <strong>Lecture des sources…</strong>
          </div>
        ) : state === 'error' ? (
          <div className="catalog-state" role="alert">
            <Icon name="lock" />
            <strong>Sources indisponibles</strong>
            <p>{error}</p>
          </div>
        ) : sources.length === 0 ? (
          <div className="catalog-state">
            <Icon name="catalog" />
            <strong>Aucune source visible</strong>
            <p>Aucune source de données n’est enregistrée pour cette unité.</p>
          </div>
        ) : (
          sources.map((source) => (
            <button
              aria-current={source.id === selectedId ? 'true' : undefined}
              key={source.id}
              type="button"
              onClick={() => {
                onSelect(source.id);
              }}
            >
              <Icon name="database" />
              <span>
                <strong>{source.name}</strong>
                <small>{kindLabels[source.kind]}</small>
              </span>
              <StatusBadge tone={statusTone[source.status]}>
                {statusLabels[source.status]}
              </StatusBadge>
            </button>
          ))
        )}
      </aside>

      <section className="system-detail" aria-labelledby="system-detail-title">
        {selected ? (
          <>
            <header>
              <div>
                <span>{kindLabels[selected.kind]}</span>
                <h2 id="system-detail-title">{selected.name}</h2>
                <p>Clé technique : {selected.key}</p>
              </div>
              <StatusBadge tone={statusTone[selected.status]}>
                {statusLabels[selected.status]}
              </StatusBadge>
            </header>

            <div className="system-facts">
              <article>
                <Icon name="people" />
                <span>
                  <small>Unité propriétaire</small>
                  <strong title={selected.owner_unit_id}>
                    {selected.owner_unit_id.slice(0, 8)}…
                  </strong>
                </span>
              </article>
              <article>
                <Icon name="governance" />
                <span>
                  <small>Système source déclaré</small>
                  <strong title={selected.system_artifact_id ?? undefined}>
                    {selected.system_artifact_id
                      ? `${selected.system_artifact_id.slice(0, 8)}…`
                      : 'Non rattaché'}
                  </strong>
                </span>
              </article>
              <article>
                <Icon name="key" />
                <span>
                  <small>Identifiants</small>
                  <strong>{selected.has_credentials ? 'Référencés' : 'Aucun'}</strong>
                </span>
              </article>
            </div>

            <div className="authority-heading">
              <div>
                <h3>Autorité de cette source</h3>
                <p>
                  Une deuxième source exclusive sur le même périmètre bloquerait la publication.
                </p>
              </div>
              <button
                disabled
                title="Disponible après connexion du formulaire à l’API"
                type="button"
              >
                Ajouter une source · bientôt
              </button>
            </div>

            <aside className="no-copy-proof">
              <Icon name="shield" />
              <div>
                <strong>Une autorité limitée aux données déclarées.</strong>
                <p>
                  Cette source fait foi pour son propre périmètre uniquement. Les données d’autres
                  systèmes ne sont ni dupliquées, ni réinterprétées ici.
                </p>
              </div>
            </aside>
          </>
        ) : (
          <div className="catalog-state catalog-state--detail">
            <Icon name="catalog" />
            <h2 id="system-detail-title">Aucune source sélectionnée</h2>
            <p>Choisissez une source pour afficher son détail de gouvernance.</p>
          </div>
        )}
      </section>
    </main>
  );
}

export function SystemAuthorityWorkbench() {
  const [sources, setSources] = useState<DataSourceSummary[]>([]);
  const [state, setState] = useState<RequestState>('loading');
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState('');

  useEffect(() => {
    let isActive = true;
    setState('loading');
    setError('');
    void platformRequest<{ items: DataSourceSummary[] }>('/data/organization/group/sources')
      .then((value) => {
        if (!isActive) return;
        setSources(value.items);
        setSelectedId((current) =>
          value.items.some((item) => item.id === current) ? current : (value.items[0]?.id ?? ''),
        );
        setState('ready');
      })
      .catch((failure: unknown) => {
        if (!isActive) return;
        setError(failure instanceof Error ? failure.message : 'Les sources sont indisponibles.');
        setState('error');
      });
    return () => {
      isActive = false;
    };
  }, []);

  return (
    <SystemAuthorityWorkbenchView
      error={error}
      selectedId={selectedId}
      sources={sources}
      state={state}
      onSelect={setSelectedId}
    />
  );
}
