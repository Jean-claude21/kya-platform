# KYA-Platform SDK

Private typed client for applications that consume KYA-Platform Business APIs.

```bash
pnpm add @jean-claude21/kya-platform-sdk
```

The consuming repository must authenticate to GitHub Packages and map the owner scope:

```ini
@jean-claude21:registry=https://npm.pkg.github.com
```

```ts
import { KyaPlatformClient } from '@jean-claude21/kya-platform-sdk';

const kya = new KyaPlatformClient({
  apiUrl: 'https://api.kya-platform.vttlife.com',
  getAccessToken: obtainNeonAccessToken,
  getActiveContext: () => ({ unitId: 'group' }),
});
```

Applications provide the Neon Auth token and selected organizational context. The SDK attaches
them to requests; KYA-Platform and OpenFGA remain the authorization authority.

The same client exposes the permission-filtered application registry and KYA Core context:

```ts
const session = await kya.getSession();
const applications = await kya.listApplications();
const activeUnit = await kya.getOrganizationalUnit(session.active_unit_id);

for (const application of applications.items) {
  if (application.enabled && application.effective_permissions.includes('use')) {
    console.log(application.name, application.launch_url);
  }
}
```

Applications may provide `onTelemetry` to observe status, latency and KYA correlation identifiers.
Telemetry events never contain the access token or response payload.
