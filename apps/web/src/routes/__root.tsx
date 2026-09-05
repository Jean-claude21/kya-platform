import { HeadContent, Outlet, Scripts, createRootRoute } from '@tanstack/react-router';
import type { ReactNode } from 'react';

import '@kya/design-system/styles.css';
import '../styles/app.css';

const DIRECTION_CONTRACT =
  'THESIS: Le réseau des capacités KYA devient l’interface. OWN-WORLD: Tableau de conduite énergétique lumineux. STORY: situer, comprendre, trouver et agir. FIRST VIEWPORT: commande, réseau en six couches et décisions. FORM: position 4, seed 4b456a6c. FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md';

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: 'utf-8' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      { title: 'KYA Platform — Réseau de capacités' },
      {
        name: 'description',
        content: 'Catalogue gouverné des capacités numériques de KYA-Energy Group.',
      },
    ],
  }),
  notFoundComponent: NotFound,
  component: RootComponent,
});

function NotFound() {
  return (
    <main className="not-found">
      <h1>Page introuvable</h1>
      <p>Cette destination n’est pas encore disponible dans KYA Platform.</p>
      <a href="/">Revenir au réseau de capacités</a>
    </main>
  );
}

function RootComponent() {
  return (
    <RootDocument>
      <Outlet />
    </RootDocument>
  );
}

function RootDocument({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="fr">
      <head>
        <HeadContent />
      </head>
      <body data-direction-contract={DIRECTION_CONTRACT}>
        {/*
          THESIS: Le réseau des capacités KYA devient l'interface; il refuse le tableau de bord SaaS en tuiles sans relations.
          OWN-WORLD: Fond chaud, surfaces blanches, vert structurel, orange d'action, lignes fines de schéma énergétique et états explicites.
          STORY: Le collaborateur situe les sources, comprend la chaîne autorisée, trouve une capacité puis agit ou décide.
          FIRST VIEWPORT: Commande globale en haut; réseau en six couches sur les deux tiers; file de décisions à droite; recherche primaire toujours visible.
          FORM: Tableau de conduite énergétique, position 4 de la liste ancrée; seed 4b456a6c.
          FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
        */}
        {children}
        <Scripts />
      </body>
    </html>
  );
}
