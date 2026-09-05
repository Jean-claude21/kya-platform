import { useMemo, useState } from 'react';

import { Icon, StatusBadge } from '@kya/design-system';

const events = [
  {
    id: '01A06F70-01',
    at: '5 sept. · 10:18',
    action: 'Artefact publié',
    actor: 'Afi A. · CVSI',
    actorContext: 'Direction CVSI',
    environment: 'Test',
    decision: 'Autorisée',
    outcome: 'Réussie',
    target: 'Skill Formats documentaires · v1.0.0',
    correlation: '01A06F70…F23',
    tone: 'healthy' as const,
  },
  {
    id: '01A06F70-02',
    at: '5 sept. · 10:12',
    action: 'Approbation métier',
    actor: 'Direction Communication',
    actorContext: 'Direction Communication',
    environment: 'Test',
    decision: 'Approuvée',
    outcome: 'Réussie',
    target: 'Demande de publication PR-0042',
    correlation: '01A06F70…F23',
    tone: 'healthy' as const,
  },
  {
    id: '01A06F70-03',
    at: '5 sept. · 10:05',
    action: 'Contrôles techniques',
    actor: 'service:publication-worker',
    actorContext: 'Service CVSI',
    environment: 'Test',
    decision: 'Conforme',
    outcome: 'Réussie',
    target: 'Digest sha256 · manifeste · propriétaires',
    correlation: '01A06F70…F23',
    tone: 'healthy' as const,
  },
  {
    id: '01A06F70-04',
    at: '5 sept. · 09:58',
    action: 'Candidat soumis',
    actor: 'Kossi D. · Communication',
    actorContext: 'Direction Communication',
    environment: 'Test',
    decision: 'Reçue',
    outcome: 'En validation',
    target: 'Skill Formats documentaires · v1.0.0',
    correlation: '01A06F70…F23',
    tone: 'attention' as const,
  },
] as const;

const eventsByWorkspace: Readonly<Record<string, readonly (typeof events)[number][]>> = {
  platform: events,
};

export function AuditTimeline({ workspaceKey }: { workspaceKey: string }) {
  const [query, setQuery] = useState('');
  const visibleEvents = useMemo(() => {
    const scopedEvents = eventsByWorkspace[workspaceKey] ?? [];
    const normalized = query.trim().toLocaleLowerCase('fr');
    if (!normalized) return scopedEvents;
    return scopedEvents.filter((event) =>
      `${event.action} ${event.actor} ${event.target} ${event.correlation}`
        .toLocaleLowerCase('fr')
        .includes(normalized),
    );
  }, [query, workspaceKey]);

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
          <StatusBadge tone="neutral">Données de démonstration</StatusBadge>
          <StatusBadge tone="restricted">Vue métadonnées uniquement</StatusBadge>
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
            <dt>Unité active</dt>
            <dd>Direction CVSI</dd>
          </div>
          <div>
            <dt>Mandat</dt>
            <dd>audit.metadata</dd>
          </div>
        </dl>
        <label>
          <span className="sr-only">Filtrer les événements</span>
          <Icon name="search" />
          <input
            value={query}
            placeholder="Action, acteur, cible…"
            onChange={(event) => {
              setQuery(event.target.value);
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
            <h2 id="audit-events-title">Historique de l’artefact</h2>
            <p>
              {visibleEvents.length} preuve(s), ordonnées de la plus récente à la plus ancienne.
            </p>
          </div>
          {visibleEvents.length > 0 && (
            <span className="audit-correlation">Corrélation 01A06F70…F23</span>
          )}
        </header>

        <ol className="audit-timeline">
          {visibleEvents.map((event) => (
            <li key={event.id}>
              <span className={`audit-marker audit-marker--${event.tone}`} aria-hidden="true">
                <Icon name={event.tone === 'healthy' ? 'check' : 'branch'} />
              </span>
              <article>
                <header>
                  <div>
                    <time>{event.at}</time>
                    <h3>{event.action}</h3>
                  </div>
                  <StatusBadge tone={event.tone}>{event.outcome}</StatusBadge>
                </header>
                <p>{event.target}</p>
                <dl>
                  <div>
                    <dt>Acteur</dt>
                    <dd>{event.actor}</dd>
                  </div>
                  <div>
                    <dt>Décision</dt>
                    <dd>{event.decision}</dd>
                  </div>
                  <div>
                    <dt>Corrélation</dt>
                    <dd>{event.correlation}</dd>
                  </div>
                  <div>
                    <dt>Contexte</dt>
                    <dd>{event.actorContext}</dd>
                  </div>
                  <div>
                    <dt>Environnement</dt>
                    <dd>{event.environment}</dd>
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
      </section>
    </main>
  );
}
