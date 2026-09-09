import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { SystemAuthorityWorkbench } from './system-authority-workbench';

describe('system authority workbench', () => {
  it('makes ownership, authority and no-copy semantics explicit', () => {
    const html = renderToStaticMarkup(<SystemAuthorityWorkbench />);

    expect(html).toContain('KYA-Platform');
    expect(html).toContain('Source qui fait foi');
    expect(html).toContain('limitée aux données du Hub');
    expect(html).toContain('bloquerait la publication');
    expect(html).not.toContain('données de démonstration');
  });

  it('does not imitate a connected authority mutation', () => {
    const html = renderToStaticMarkup(<SystemAuthorityWorkbench />);

    expect(html).toContain('Ajouter un système · bientôt');
    expect(html).toContain('disabled');
  });
});
