import { useEffect, useState } from 'react';

import { Icon, StatusBadge } from '@kya/design-system';

import { platformRequest } from '../../platform/api';

type SecretKind = 'personal' | 'team' | 'service' | 'application' | 'environment';
type SecretStatus = 'active' | 'rotation_due' | 'revoked';

export type SecretReferenceSummary = {
  id: string;
  kind: SecretKind;
  provider: string;
  locator: string;
  key_name: string;
  owner_scope: string;
  purpose: string;
  environment: string;
  status: SecretStatus;
  created_at: string;
  rotated_at: string | null;
  expires_at: string | null;
};

type RequestState = 'loading' | 'ready' | 'error';

const statusLabels: Record<SecretStatus, string> = {
  active: 'Actif',
  rotation_due: 'Rotation requise',
  revoked: 'Révoqué',
};

const statusTone: Record<SecretStatus, 'healthy' | 'attention' | 'restricted'> = {
  active: 'healthy',
  rotation_due: 'attention',
  revoked: 'restricted',
};

function formatDate(value: string | null): string {
  if (!value) return '—';
  return new Date(value).toLocaleString('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

export function SecretAccessWorkbenchView({
  error,
  references,
  selectedId,
  state,
  onSelect,
}: {
  error: string;
  references: SecretReferenceSummary[];
  selectedId: string;
  state: RequestState;
  onSelect: (id: string) => void;
}) {
  const selected = references.find((reference) => reference.id === selectedId) ?? null;

  return (
    <main className="secrets-page">
      <section className="secrets-intro" aria-labelledby="secrets-title">
        <div>
          <h1 id="secrets-title">Accès techniques sans révéler les clés</h1>
          <p>
            KYA conserve ici les responsabilités et autorisations. Les valeurs restent dans
            Infisical et ne sont jamais affichées.
          </p>
        </div>
        <StatusBadge tone="restricted">Filtré par droits</StatusBadge>
      </section>

      <section className="secret-register" aria-labelledby="secret-register-title">
        <header>
          <div>
            <h2 id="secret-register-title">Références accessibles</h2>
            <p>Liste filtrée par rôle, espace actif et environnement.</p>
          </div>
          <button disabled title="Disponible après connexion du formulaire à l’API" type="button">
            Ajouter une référence · bientôt
          </button>
        </header>

        {state === 'loading' ? (
          <div className="catalog-state" role="status">
            <Icon name="activity" />
            <strong>Lecture des références…</strong>
          </div>
        ) : state === 'error' ? (
          <div className="catalog-state" role="alert">
            <Icon name="lock" />
            <strong>Références indisponibles</strong>
            <p>{error}</p>
          </div>
        ) : references.length === 0 ? (
          <div className="catalog-state">
            <Icon name="catalog" />
            <strong>Aucune référence visible</strong>
            <p>Aucune référence de secret n’est partagée avec votre unité active.</p>
          </div>
        ) : (
          <div className="secret-reference-list">
            {references.map((reference) => (
              <button
                aria-current={reference.id === selectedId ? 'true' : undefined}
                key={reference.id}
                type="button"
                onClick={() => {
                  onSelect(reference.id);
                }}
              >
                <Icon name="shield" />
                <div>
                  <strong>{reference.key_name}</strong>
                  <span>
                    {reference.kind} · {reference.owner_scope}
                  </span>
                </div>
                <StatusBadge tone={statusTone[reference.status]}>
                  {statusLabels[reference.status]}
                </StatusBadge>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="secret-detail" aria-labelledby="secret-detail-title">
        {selected ? (
          <>
            <header>
              <div>
                <h2 id="secret-detail-title">{selected.key_name}</h2>
                <p>
                  Référence {selected.provider} uniquement. La valeur n’entre jamais dans
                  KYA-Platform.
                </p>
              </div>
              <StatusBadge tone={statusTone[selected.status]}>
                {statusLabels[selected.status]}
              </StatusBadge>
            </header>

            <dl className="secret-facts">
              <div>
                <dt>Bénéficiaire</dt>
                <dd>{selected.owner_scope}</dd>
              </div>
              <div>
                <dt>Finalité</dt>
                <dd>{selected.purpose}</dd>
              </div>
              <div>
                <dt>Environnement</dt>
                <dd>{selected.environment}</dd>
              </div>
              <div>
                <dt>Créée le</dt>
                <dd>{formatDate(selected.created_at)}</dd>
              </div>
              <div>
                <dt>Expiration</dt>
                <dd>{formatDate(selected.expires_at)}</dd>
              </div>
            </dl>

            <aside className="secret-boundary">
              <Icon name="shield" />
              <div>
                <strong>La clé ne peut pas être révélée.</strong>
                <p>
                  Le service autorisé reçoit un usage court, limité à sa finalité. Une tentative en
                  production, après expiration ou après révocation est refusée et auditée.
                </p>
              </div>
            </aside>

            <div className="secret-actions">
              <button disabled title="Disponible après raccordement du formulaire" type="button">
                Révoquer en urgence · bientôt
              </button>
              <span>Aucune valeur secrète disponible dans cette interface.</span>
            </div>
          </>
        ) : (
          <div className="catalog-state catalog-state--detail">
            <Icon name="catalog" />
            <h2 id="secret-detail-title">Aucune référence sélectionnée</h2>
            <p>Choisissez une référence pour afficher ses détails de gouvernance.</p>
          </div>
        )}
      </section>
    </main>
  );
}

export function SecretAccessWorkbench() {
  const [references, setReferences] = useState<SecretReferenceSummary[]>([]);
  const [state, setState] = useState<RequestState>('loading');
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState('');

  useEffect(() => {
    let isActive = true;
    setState('loading');
    setError('');
    void platformRequest<{ items: SecretReferenceSummary[] }>('/secrets')
      .then((value) => {
        if (!isActive) return;
        setReferences(value.items);
        setSelectedId((current) =>
          value.items.some((item) => item.id === current) ? current : (value.items[0]?.id ?? ''),
        );
        setState('ready');
      })
      .catch((failure: unknown) => {
        if (!isActive) return;
        setError(
          failure instanceof Error ? failure.message : 'Les références sont indisponibles.',
        );
        setState('error');
      });
    return () => {
      isActive = false;
    };
  }, []);

  return (
    <SecretAccessWorkbenchView
      error={error}
      references={references}
      selectedId={selectedId}
      state={state}
      onSelect={setSelectedId}
    />
  );
}

