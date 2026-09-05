import { createFileRoute } from '@tanstack/react-router';

import { PlatformShell } from '../screens/platform-shell';
import { AuthGate } from '../auth/auth-gate';

export const Route = createFileRoute('/')({
  component: () => (
    <AuthGate>
      <PlatformShell />
    </AuthGate>
  ),
});
