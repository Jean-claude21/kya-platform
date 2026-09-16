import { createFileRoute } from '@tanstack/react-router';
import { useEffect, useState } from 'react';

import { KyaMark } from '@kya/design-system';

import { AuthGate } from '../auth/auth-gate';
import { getAccessToken } from '../auth/client';

type Consent = {
  client_name: string;
  scopes: string[];
  resource: string;
  expires_at: string;
};

const scopeCopy: Record<string, { title: string; detail: string }> = {
  'catalog:read': {
    title: 'Consulter le catalogue autorisé',
    detail: 'Voir uniquement les Skills, MCP et applications accessibles dans votre contexte.',
  },
  'catalog:install': {
    title: 'Demander une installation ou une mise à jour',
    detail: 'Créer une demande traçable ; les validations KYA restent applicables.',
  },
  'catalog:publish': {
    title: 'Soumettre un candidat à publication',
    detail: 'Transmettre une version pour revue, sans contourner l’approbation.',
  },
};

export const Route = createFileRoute('/oauth/consent')({
  validateSearch: (search: Record<string, unknown>) => ({
    request: typeof search.request === 'string' ? search.request : '',
  }),
  component: () => (
    <AuthGate>
      <ConsentPage />
    </AuthGate>
  ),
});

function ConsentPage() {
  const [consent, setConsent] = useState<Consent | null>(null);
  const [error, setError] = useState('');
  const [pending, setPending] = useState<'approve' | 'deny' | null>(null);
  const { request: handle } = Route.useSearch();

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        if (!handle) throw new Error('La demande OAuth est absente. Reprenez la connexion MCP.');
        const token = await getAccessToken();
        const apiUrl = import.meta.env.VITE_KYA_API_URL;
        if (!token || !apiUrl) throw new Error('La session KYA ou l’API est indisponible.');
        const response = await fetch(
          `${apiUrl.replace(/\/$/, '')}/api/v1/oauth/requests/${encodeURIComponent(handle)}`,
          {
            headers: { Authorization: `Bearer ${token}`, 'X-KYA-Unit-ID': 'group' },
            signal: controller.signal,
          },
        );
        if (!response.ok) throw new Error('Cette demande est expirée ou déjà traitée.');
        setConsent((await response.json()) as Consent);
      } catch (failure) {
        if (!controller.signal.aborted) {
          setError(failure instanceof Error ? failure.message : 'La demande est indisponible.');
        }
      }
    }
    void load();
    return () => {
      controller.abort();
    };
  }, [handle]);

  async function decide(decision: 'approve' | 'deny') {
    setPending(decision);
    setError('');
    try {
      const token = await getAccessToken();
      const apiUrl = import.meta.env.VITE_KYA_API_URL;
      if (!token || !apiUrl) throw new Error('La session KYA ou l’API est indisponible.');
      const response = await fetch(
        `${apiUrl.replace(/\/$/, '')}/api/v1/oauth/requests/${encodeURIComponent(handle)}/${decision}`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'X-KYA-Unit-ID': 'group' },
        },
      );
      if (!response.ok) throw new Error('La décision n’a pas pu être enregistrée.');
      const result = (await response.json()) as { redirect_url: string };
      window.location.assign(result.redirect_url);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'La décision a échoué.');
      setPending(null);
    }
  }

  return (
    <main className="oauth-consent-page">
      <section className="oauth-visual" aria-hidden="true">
        <img src="/images/auth/ai-authorization.png" alt="" />
        <div>
          <KyaMark />
          <p>
            Une connexion explicite.
            <br />
            Des droits limités et révocables.
          </p>
        </div>
      </section>
      <section className="oauth-consent-sheet" aria-labelledby="oauth-consent-title">
        <header>
          <KyaMark />
          <div>
            <h1 id="oauth-consent-title">Autoriser un environnement IA</h1>
            <p>
              KYA contrôle chaque action selon votre rôle et l’unité active, même après cette
              autorisation.
            </p>
          </div>
        </header>

        {error ? (
          <div className="oauth-consent-error" role="alert">
            <h2>Connexion interrompue</h2>
            <p>{error}</p>
          </div>
        ) : !consent ? (
          <p className="oauth-consent-loading" aria-live="polite">
            Vérification de la demande…
          </p>
        ) : (
          <>
            <div className="oauth-client-line">
              <span>Client demandeur</span>
              <strong>{consent.client_name}</strong>
            </div>
            <div className="oauth-scope-list">
              <h2>Droits demandés</h2>
              {consent.scopes.map((scope) => {
                const copy = scopeCopy[scope] ?? {
                  title: scope,
                  detail: 'Droit déclaré par ce client MCP.',
                };
                return (
                  <article key={scope}>
                    <span aria-hidden="true" />
                    <div>
                      <strong>{copy.title}</strong>
                      <p>{copy.detail}</p>
                    </div>
                  </article>
                );
              })}
            </div>
            <p className="oauth-consent-boundary">
              Aucun mot de passe, secret d’entreprise ou droit hors de votre rôle ne sera transmis
              au client.
            </p>
            <footer>
              <button
                type="button"
                className="oauth-deny"
                disabled={pending !== null}
                onClick={() => void decide('deny')}
              >
                {pending === 'deny' ? 'Refus en cours…' : 'Refuser'}
              </button>
              <button
                type="button"
                className="oauth-approve"
                disabled={pending !== null}
                onClick={() => void decide('approve')}
              >
                {pending === 'approve' ? 'Autorisation en cours…' : 'Autoriser et revenir'}
              </button>
            </footer>
          </>
        )}
      </section>
    </main>
  );
}
