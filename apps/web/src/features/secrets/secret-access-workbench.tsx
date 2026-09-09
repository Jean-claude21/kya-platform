import { Icon, StatusBadge } from '@kya/design-system';

const references = [
  {
    name: 'Accès Frappe — lecture clients',
    kind: 'Service',
    owner: 'CVSI',
    environment: 'Preview',
    purpose: 'Lire les clients autorisés',
    expires: '5 sept. 2026 · 12:00',
  },
] as const;

export function SecretAccessWorkbench() {
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
        <StatusBadge tone="restricted">Données de démonstration</StatusBadge>
      </section>

      <section className="secret-register" aria-labelledby="secret-register-title">
        <header>
          <div>
            <h2 id="secret-register-title">Références accessibles</h2>
            <p>Liste filtrée par rôle, espace actif et environnement.</p>
          </div>
          <button disabled title="Disponible après connexion de l’écriture à Neon" type="button">
            Ajouter une référence · bientôt
          </button>
        </header>

        <div className="secret-reference-list">
          {references.map((reference) => (
            <article key={reference.name}>
              <Icon name="shield" />
              <div>
                <strong>{reference.name}</strong>
                <span>
                  {reference.kind} · {reference.owner}
                </span>
              </div>
              <StatusBadge tone="healthy">Actif</StatusBadge>
            </article>
          ))}
        </div>
      </section>

      <section className="secret-detail" aria-labelledby="secret-detail-title">
        <header>
          <div>
            <h2 id="secret-detail-title">Accès Frappe — lecture clients</h2>
            <p>Référence Infisical uniquement. La valeur n’entre jamais dans KYA-Platform.</p>
          </div>
          <StatusBadge tone="attention">Expire bientôt</StatusBadge>
        </header>

        <dl className="secret-facts">
          <div>
            <dt>Bénéficiaire</dt>
            <dd>service:frappe-reader</dd>
          </div>
          <div>
            <dt>Finalité</dt>
            <dd>{references[0].purpose}</dd>
          </div>
          <div>
            <dt>Environnement</dt>
            <dd>{references[0].environment}</dd>
          </div>
          <div>
            <dt>Expiration</dt>
            <dd>{references[0].expires}</dd>
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
          <button disabled title="Disponible après raccordement Infisical" type="button">
            Révoquer en urgence · bientôt
          </button>
          <span>Aucune valeur secrète disponible dans cette interface.</span>
        </div>
      </section>
    </main>
  );
}
