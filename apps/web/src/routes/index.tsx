import { createFileRoute } from '@tanstack/react-router';

import { PlatformShell } from '../screens/platform-shell';

export const Route = createFileRoute('/')({ component: PlatformShell });
