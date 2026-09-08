# Architecture overview

KYA Platform is a modular monolith with multiple delivery surfaces. The Web application, Business
API, MCP gateway and workers reuse the same application services and domain rules.

```mermaid
flowchart TB
    People[Employees and partners]
    AI[Claude, ChatGPT and coding environments]
    Web[TanStack Web application]
    API[FastAPI Business API]
    MCP[Governed MCP gateway]
    Workers[Workers and scheduled routines]
    App[Application services]
    Domain[KYA domains and contracts]
    Neon[(Neon Postgres, Auth and Storage)]
    FGA[OpenFGA authorization]
    Secrets[Infisical secrets]
    External[External systems and Frappe adapters]

    People --> Web
    People --> AI
    AI --> MCP
    Web --> API
    MCP --> App
    API --> App
    Workers --> App
    App --> Domain
    App --> FGA
    App --> Secrets
    App --> Neon
    App --> External
```

## Dependency direction

The protected source dependency direction is:

```text
API / MCP / workers → application → domain and contracts
infrastructure implements application-facing ports
```

Architecture tests reject domain imports from outer layers and application imports from delivery or
infrastructure layers.
