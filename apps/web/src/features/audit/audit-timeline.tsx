import { useEffect, useMemo, useState } from 'react';

import { Icon, StatusBadge } from '@kya/design-system';

import { platformRequest } from '../../platform/api';

export type AuditEvent = {
  id: string;
  occurred_at: string;
  actor_id: string | null;
  actor_context: Record<string, unknown>;
  action: string;
  target_type: string;
  target_id: string;
  scope: string;
  environment: string | null;
  decision: string | null;
  outcome: string;
  correlation_id: string;
  causation_id: string | null;
  metadata: Record<string, unknown>;
  protected_content: Record<string, unknown> | null;
};

type RequestState = 'loading' | 'ready' | 'error';

function outcomeTone(outcome: string): 'healthy' | 'attention' | 'restricted' {
  const normalized = outcome.toLocaleLowerCase('fr');
  if (normalized.includes('échec') || normalized.includes('refus')) return 'restricted';
  if (normalized.includes('validation') || normalized.includes('attente')) return 'attention';
  return 'healthy';
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' });
}

function actorLabel(event: AuditEvent): string {
  if (event.actor_id) return event.actor_id.slice(0, 8) + '…';
  const label = event.actor_context.label;
  return typeof label === 'string' ? label : 'Acteur système';
}

export function AuditTimelineView({
  contentMode,
  error,
  events,
  query,
  state,
  workspaceKey,
  onQueryChange,
}: {
  contentMode: string;
  error: string;
  events: AuditEvent[];
  query: string;
  state: RequestState;
  workspaceKey: string;
  onQueryChange: (value: string) => void;
}) {
  const visibleEvents = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('fr');
    if (!normalized) return events;
    return events.filter((event) =>
      `${event.action} ${event.target_type} ${event.target_id} ${event.correlation_id}`
        .toLocaleLowerCase('fr')
        .includes(normalized),
    );
  }, [events, query]);

  return (
    <main className="audit-page">
      <section className="audit-intro" aria-labelledby="audit-title">
        <div>
          <h1 id="audit-title">Piste d’audit</h1>
          <p>
            Reconstituer les demandes, décisions et résultats sans créer d’administrateur omnipotent
            ni révéler de secret.
          </p>
        </div>
        <div className="audit-intro-badges">
          <StatusBadge tone="restricted">
            {contentMode === 'protected' ? 'Contenu métier visible' : 'Vue métadonnées uniquement'}
          </StatusBadge>
        </div>
      </section>

      <aside className="audit-filters" aria-labelledby="audit-filter-title">
        <h2 id="audit-filter-title">Périmètre contrôlé</h2>
        <dl>
          <div>
            <dt>Espace</dt>
            <dd>{workspaceKey}</dd>
          </div>
          <div>
            <dt>Mandat</dt>
            <dd>{contentMode === 'protected' ? 'audit.content' : 'audit.metadata'}</dd>
          </div>
        </dl>
        <label>
          <span className="sr-only">Filtrer les événements</span>
          <Icon name="search" />
          <input
            value={query}
            placeholder="Action, cible, corrélation…"
            onChange={(event) => {
              onQueryChange(event.target.value);
            }}
          />
        </label>
        <div className="audit-separation-note">
          <Icon name="shield" />
          <p>Le contenu métier reste masqué. Un mandat séparé est exigé pour le consulter.</p>
        </div>
      </aside>

      <section className="audit-events" aria-labelledby="audit-events-title">
        <header>
          <div>
            <h2 id="audit-events-title">Historique de l’espace</h2>
            <p>
              {state === 'ready'
                ? `${String(visibleEvents.length)} preuve(s), ordonnées de la plus récente à la plus ancienne.`
                : 'Lecture sécurisée en cours'}
            </p>
          </div>
        </header>

        {state === 'loading' ? (
          <div className="catalog-state" role="status">
            <Icon name="activity" />
            <strong>Lecture de la piste d’audit…</strong>
          </div>
        ) : state === 'error' ? (
          <div className="catalog-state" role="alert">
            <Icon name="lock" />
            <strong>Piste d’audit indisponible</strong>
            <p>{error}</p>
          </div>
        ) : (
          <>
            <ol className="audit-timeline">
              {visibleEvents.map((event) => (
                <li key={event.id}>
                  <span
                    className={`audit-marker audit-marker--${outcomeTone(event.outcome)}`}
                    aria-hidden="true"
                  >
                    <Icon name={outcomeTone(event.outcome) === 'healthy' ? 'check' : 'branch'} />
                  </span>
                  <article>
                    <header>
                      <div>
                        <time>{formatDate(event.occurred_at)}</time>
                        <h3>{event.action}</h3>
                      </div>
                      <StatusBadge tone={outcomeTone(event.outcome)}>{event.outcome}</StatusBadge>
                    </header>
                    <p>
                      {event.target_type} · {event.target_id}
                    </p>
                    <dl>
                      <div>
                        <dt>Acteur</dt>
                        <dd>{actorLabel(event)}</dd>
                      </div>
                      <div>
                        <dt>Décision</dt>
                        <dd>{event.decision ?? '—'}</dd>
                      </div>
                      <div>
                        <dt>Corrélation</dt>
                        <dd title={event.correlation_id}>{event.correlation_id.slice(0, 8)}…</dd>
                      </div>
                      <div>
                        <dt>Environnement</dt>
                        <dd>{event.environment ?? '—'}</dd>
                      </div>
                    </dl>
                  </article>
                </li>
              ))}
            </ol>
            {visibleEvents.length === 0 && (
              <p className="audit-empty" role="status">
                Aucun événement autorisé ne correspond à cet espace et à ce filtre.
              </p>
            )}
          </>
        )}
      </section>
    </main>
  );
}

export function AuditTimeline({ workspaceKey }: { workspaceKey: string }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [contentMode, setContentMode] = useState('metadata_only');
  const [state, setState] = useState<RequestState>('loading');
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');

  useEffect(() => {
    let isActive = true;
    setState('loading');
    setError('');
    void platformRequest<{ items: AuditEvent[]; content_mode: string }>(
      `/audit/workspaces/${encodeURIComponent(workspaceKey)}/events`,
    )
      .then((value) => {
        if (!isActive) return;
        setEvents(value.items);
        setContentMode(value.content_mode);
        setState('ready');
      })
      .catch((failure: unknown) => {
        if (!isActive) return;
        setError(failure instanceof Error ? failure.message : 'La piste d’audit est indisponible.');
        setState('error');
      });
    return () => {
      isActive = false;
    };
  }, [workspaceKey]);

  return (
    <AuditTimelineView
      contentMode={contentMode}
      error={error}
      events={events}
      query={query}
      state={state}
      workspaceKey={workspaceKey}
      onQueryChange={setQuery}
    />
  );
}
