import { createFileRoute } from '@tanstack/react-router';

import { PlatformShell } from '../screens/platform-shell';
import { AuthGate } from '../auth/auth-gate';

export const Route = createFileRoute('/')({
  component: () =>
    import.meta.env.DEV && import.meta.env.VITE_KYA_PREVIEW_MODE === 'app' ? (
      <PlatformShell />
    ) : (
      <AuthGate>
        <PlatformShell />
      </AuthGate>
    ),
});
