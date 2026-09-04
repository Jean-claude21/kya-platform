import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { SecretAccessWorkbench } from './secret-access-workbench';

describe('secret access workbench', () => {
  it('explains the non-reveal boundary and scoped use', () => {
    const html = renderToStaticMarkup(<SecretAccessWorkbench />);

    expect(html).toContain('sans révéler les clés');
    expect(html).toContain('La clé ne peut pas être révélée');
    expect(html).toContain('service:frappe-reader');
    expect(html).toContain('Révoquer en urgence · bientôt');
    expect(html).toContain('disabled');
  });
});
