# API Reference

*REST API for programmatic access*

The SimCash backend exposes a full REST API powered by FastAPI. The interactive
Swagger UI provides auto-generated documentation for every endpoint, including
request/response schemas and a built-in "Try it out" feature.

## Swagger UI

Open the API docs in a new tab to explore all available endpoints:

- [📄 Open API Documentation (Swagger UI) →](/api/docs)
- [📘 Open API Documentation (ReDoc) →](/api/redoc)

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/games` | Create a new game session |
| `GET` | `/api/games/{id}` | Get game status and results |
| `POST` | `/api/simulate` | Run a one-shot simulation |
| `GET` | `/api/scenarios` | List available scenarios |
| `GET` | `/api/health` | Health check |

> ℹ️ The API accepts scenario YAML and policy JSON in the formats documented in the
> **Schema Reference** section. All monetary values are integers (cents).
