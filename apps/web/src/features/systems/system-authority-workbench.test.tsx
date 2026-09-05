import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { SystemAuthorityWorkbench } from './system-authority-workbench';

describe('system authority workbench', () => {
  it('makes ownership, authority and no-copy semantics explicit', () => {
    const html = renderToStaticMarkup(<SystemAuthorityWorkbench />);

    expect(html).toContain('Frappe / ERPNext');
    expect(html).toContain('Source qui fait foi');
    expect(html).toContain('pas les fiches clients');
    expect(html).toContain('bloquerait la publication');
  });

  it('does not imitate a connected authority mutation', () => {
    const html = renderToStaticMarkup(<SystemAuthorityWorkbench />);

    expect(html).toContain('Déclarer une autorité · bientôt');
    expect(html).toContain('disabled');
  });
});
