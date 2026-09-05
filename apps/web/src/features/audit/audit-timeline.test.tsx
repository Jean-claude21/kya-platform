import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { AuditTimeline } from './audit-timeline';

describe('audit timeline', () => {
  it('shows scoped evidence and explains protected-content separation', () => {
    const html = renderToStaticMarkup(<AuditTimeline workspaceKey="platform" />);

    expect(html).toContain('Piste d’audit');
    expect(html).toContain('Vue métadonnées uniquement');
    expect(html).toContain('Le contenu métier reste masqué');
    expect(html).toContain('Historique de l’artefact');
    expect(html).toContain('Données de démonstration');
    expect(html).toContain('Direction CVSI');
    expect(html).toContain('Environnement');
    expect(html).toContain('Artefact publié');
    expect(html).not.toContain('secret-value');
  });

  it('does not leak events from another active workspace', () => {
    const html = renderToStaticMarkup(<AuditTimeline workspaceKey="interns" />);

    expect(html).toContain('Aucun événement autorisé');
    expect(html).not.toContain('Artefact publié');
  });
});
