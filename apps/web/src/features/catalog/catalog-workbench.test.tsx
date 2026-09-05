import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { CatalogWorkbench } from './catalog-workbench';

describe('catalog workbench', () => {
  it('explains rights filtering and version safety', () => {
    const html = renderToStaticMarkup(<CatalogWorkbench />);

    expect(html).toContain('Filtré par droits');
    expect(html).toContain('SHA-256 vérifiée');
    expect(html).toContain('rollback');
    expect(html).toContain('données de démonstration');
  });

  it('does not imitate connected distribution writes', () => {
    const html = renderToStaticMarkup(<CatalogWorkbench />);

    expect(html).toContain('Demander la mise à jour · bientôt');
    expect(html.match(/disabled/g)?.length).toBeGreaterThanOrEqual(2);
  });
});
