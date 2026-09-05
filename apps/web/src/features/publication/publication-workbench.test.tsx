import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { PublicationWorkbench } from './publication-workbench';

describe('publication workbench', () => {
  it('makes immutable version and separation of duties explicit', () => {
    const html = renderToStaticMarkup(<PublicationWorkbench />);

    expect(html).toContain('Digest figé');
    expect(html).toContain('Même empreinte');
    expect(html).toContain('autre personne');
    expect(html).toContain('données de démonstration');
  });

  it('does not imitate connected write actions', () => {
    const html = renderToStaticMarkup(<PublicationWorkbench />);

    expect(html).toContain('Valider la revue · bientôt');
    expect(html.match(/disabled/g)?.length).toBeGreaterThanOrEqual(3);
  });
});
