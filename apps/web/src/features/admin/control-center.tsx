import { Icon, StatusBadge } from '@kya/design-system';

export type AdminTarget =
  'Organisation' | 'Core' | 'Espaces' | 'Systèmes' | 'Secrets' | 'Publications' | 'Audit';

const controls: Array<{
  target: AdminTarget;
  detail: string;
  icon: Parameters<typeof Icon>[0]['name'];
  status: string;
  tone: 'healthy' | 'attention';
}> = [
  {
    target: 'Organisation',
    detail: 'Unités, temporalité et responsabilités',
    icon: 'people',
    status: 'Connecté à Core',
    tone: 'healthy',
  },
  {
    target: 'Core',
    detail: 'Clients, projets et références partagées',
    icon: 'database',
    status: 'API active',
    tone: 'healthy',
  },
  {
    target: 'Espaces',
    detail: 'Périmètres de partage et membres',
    icon: 'folder',
    status: 'API active',
    tone: 'healthy',
  },
  {
    target: 'Systèmes',
    detail: 'Autorités de données et adaptateurs',
    icon: 'apps',
    status: 'Lecture active',
    tone: 'healthy',
  },
  {
    target: 'Secrets',
    detail: 'Références, usages et révocation',
    icon: 'key',
    status: 'Gouverné',
    tone: 'healthy',
  },
  {
    target: 'Publications',
    detail: 'Revue, approbation et versions',
    icon: 'deploy',
    status: 'Workflow actif',
    tone: 'healthy',
  },
  {
    target: 'Audit',
    detail: 'Événements et décisions traçables',
    icon: 'activity',
    status: 'Lecture active',
    tone: 'healthy',
  },
];

export function ControlCenter({ onOpen }: { onOpen: (target: AdminTarget) => void }) {
  return (
    <main className="control-page">
      <header className="page-lead">
        <div>
          <span className="eyebrow">Contrôle du socle</span>
          <h1>Administration</h1>
          <p>
            Une porte d’entrée unique vers les fonctions d’autorité, de sécurité et de traçabilité.
          </p>
        </div>
        <StatusBadge tone="healthy">Services structurants disponibles</StatusBadge>
      </header>
      <section className="control-index" aria-label="Fonctions d’administration">
        {controls.map((control) => (
          <button
            key={control.target}
            type="button"
            onClick={() => {
              onOpen(control.target);
            }}
          >
            <span className="icon-tile">
              <Icon name={control.icon} />
            </span>
            <span>
              <strong>{control.target}</strong>
              <small>{control.detail}</small>
            </span>
            <StatusBadge tone={control.tone}>{control.status}</StatusBadge>
            <Icon name="chevron" />
          </button>
        ))}
      </section>
      <aside className="admin-principle">
        <Icon name="shield" />
        <div>
          <strong>Le contrôle reste séparé de l’usage.</strong>
          <p>
            Les collaborateurs voient leurs capacités ; les administrateurs pilotent ici le socle
            selon leurs permissions.
          </p>
        </div>
      </aside>
    </main>
  );
}
