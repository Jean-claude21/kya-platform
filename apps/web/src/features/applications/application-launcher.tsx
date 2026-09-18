import { useEffect, useMemo, useState } from 'react';
import { Icon } from '@kya/design-system';
import type { KyaApplication } from '@jean-claude21/kya-platform-sdk';

import { platformClient } from '../../platform/api';

type State =
  | { status: 'loading'; items: readonly KyaApplication[]; message: string }
  | { status: 'ready'; items: readonly KyaApplication[]; message: string }
  | { status: 'error'; items: readonly KyaApplication[]; message: string };

function launch(application: KyaApplication): void {
  if (!application.enabled || !application.effective_permissions.includes('use')) return;
  if (application.launch_mode === 'new-tab') {
    window.open(application.launch_url, '_blank', 'noopener,noreferrer');
    return;
  }
  window.location.assign(application.launch_url);
}

export function ApplicationLauncher({ query = '' }: { query?: string }) {
  const [state, setState] = useState<State>({ status: 'loading', items: [], message: '' });

  useEffect(() => {
    let active = true;
    void platformClient
      .listApplications()
      .then((response) => {
        if (active) setState({ status: 'ready', items: response.items, message: '' });
      })
      .catch(() => {
        if (active) {
          setState({
            status: 'error',
            items: [],
            message: 'Le registre des applications est momentanément inaccessible. Réessayez.',
          });
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const items = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('fr');
    if (!normalized) return state.items;
    return state.items.filter((application) =>
      `${application.name} ${application.summary ?? ''}`
        .toLocaleLowerCase('fr')
        .includes(normalized),
    );
  }, [query, state.items]);

  return (
    <main className="application-launcher" aria-labelledby="applications-title">
      <header className="application-launcher__header">
        <div>
          <h1 id="applications-title">Applications</h1>
          <p>
            Ouvrez les outils métier autorisés dans votre unité active. Les droits sont recalculés
            avant chaque affichage.
          </p>
        </div>
        <span className="application-launcher__context">
          <Icon name="shield" /> Filtré par vos droits
        </span>
      </header>

      {state.status === 'loading' && (
        <div className="application-launcher__state" role="status">
          <Icon name="apps" />
          <div>
            <h2>Chargement des applications</h2>
            <p>Lecture du registre gouverné et calcul des permissions effectives.</p>
          </div>
        </div>
      )}

      {state.status === 'error' && (
        <div
          className="application-launcher__state application-launcher__state--error"
          role="alert"
        >
          <Icon name="shield" />
          <div>
            <h2>Applications indisponibles</h2>
            <p>{state.message}</p>
            <button
              type="button"
              className="signature-outline"
              onClick={() => {
                window.location.reload();
              }}
            >
              Réessayer
            </button>
          </div>
        </div>
      )}

      {state.status === 'ready' && items.length === 0 && (
        <div className="application-launcher__state" role="status">
          <Icon name="apps" />
          <div>
            <h2>Aucune application visible</h2>
            <p>
              Aucune application publiée ne correspond à votre recherche et à vos droits dans ce
              contexte.
            </p>
          </div>
        </div>
      )}

      {state.status === 'ready' && items.length > 0 && (
        <section className="application-launcher__list" aria-label="Applications autorisées">
          {items.map((application) => {
            const isUsable =
              application.enabled && application.effective_permissions.includes('use');
            return (
              <article className="application-launcher__row" key={application.artifact_id}>
                <div className="application-launcher__identity" aria-hidden="true">
                  {application.icon_url ? (
                    <img src={application.icon_url} alt="" loading="lazy" />
                  ) : (
                    <Icon name="apps" />
                  )}
                </div>
                <div className="application-launcher__copy">
                  <h2>{application.name}</h2>
                  <p>{application.summary ?? 'Application métier KYA.'}</p>
                  <div className="application-launcher__meta">
                    <span>Version {application.version}</span>
                    <span>{application.visibility}</span>
                    <span>{application.default_scope}</span>
                  </div>
                </div>
                <span className={`application-launcher__status ${isUsable ? '' : 'is-restricted'}`}>
                  <i aria-hidden="true" /> {isUsable ? 'Disponible' : 'Accès restreint'}
                </span>
                <button
                  type="button"
                  className="signature-primary application-launcher__open"
                  disabled={!isUsable}
                  title={isUsable ? undefined : "L'autorisation d'utilisation est requise."}
                  onClick={() => {
                    launch(application);
                  }}
                >
                  Ouvrir
                  <Icon name="chevron" />
                </button>
              </article>
            );
          })}
        </section>
      )}
    </main>
  );
}
