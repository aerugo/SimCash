# LLM Model Switching — Gemini 3 Pro via Vertex AI

## Goal
Wire up Gemini 3 Pro from Vertex AI as the optimization AI, with admin-switchable model selection.

## Architecture

### Current State
- `streaming_optimizer.py` hardcodes `LLMConfig(model="openai:gpt-5.2", ...)`
- `LLMConfig` (in `api/payment_simulator/llm/config.py`) already supports `google:` provider
- pydantic-ai has `google-vertex` provider for Vertex AI (uses SA credentials)
- Admin dashboard exists (Firestore-backed) but has no settings management

### Design

#### 1. Platform Settings in Firestore
Add a `platform_settings` collection (single doc `config`) to Firestore:
```json
{
  "optimization_model": "google-vertex:gemini-3.0-pro",
  "model_settings": {
    "temperature": 0.0,
    "max_tokens": 35000,
    "thinking_config": {"thinking_budget": 8000}
  },
  "available_models": [
    {"id": "google-vertex:gemini-3.0-pro", "label": "Gemini 3 Pro (Vertex AI)", "provider": "google-vertex"},
    {"id": "openai:gpt-5.2", "label": "GPT-5.2 (OpenAI)", "provider": "openai"},
    {"id": "google-vertex:gemini-2.5-flash", "label": "Gemini 2.5 Flash (Vertex AI)", "provider": "google-vertex"},
    {"id": "anthropic:claude-sonnet-4-5", "label": "Claude Sonnet 4.5", "provider": "anthropic"}
  ]
}
```

#### 2. Backend Changes
- **`web/backend/app/settings.py`** (NEW): `PlatformSettings` class
  - `get_settings()` → reads from Firestore (cached 60s)
  - `update_settings(updates, admin_email)` → writes to Firestore
  - `get_llm_config()` → returns `LLMConfig` from current settings
  - Fallback: env var `SIMCASH_DEFAULT_MODEL` or `"openai:gpt-5.2"`
- **`web/backend/app/streaming_optimizer.py`**: Replace hardcoded `LLMConfig` with `get_llm_config()`
- **`web/backend/app/main.py`**: Add settings endpoints:
  - `GET /api/settings` (admin only) — current settings
  - `PATCH /api/settings` (admin only) — update settings
  - `GET /api/settings/models` (any user) — available models list
- **`web/backend/app/admin.py`**: Keep as-is (user management)

#### 3. LLMConfig Mapping
Provider-specific settings built by `LLMConfig.to_model_settings()` (already works):
- `google-vertex:gemini-3.0-pro` → `thinking_config` for Gemini thinking
- `openai:gpt-5.2` → `reasoning_effort`, `reasoning_summary`
- `anthropic:claude-sonnet-4-5` → `thinking_budget`

The `full_model_string` property already maps `google:` → `google-gla:`.
Need to add: `google-vertex:` passes through as-is (pydantic-ai expects it).

#### 4. Frontend Changes
- **Admin Dashboard**: Add "Model Settings" section
  - Dropdown to select optimization model from available list
  - Shows current model with provider badge
  - Save button → `PATCH /api/settings`
- **Game launch UI**: Show which model is active (info badge)

#### 5. Vertex AI Auth
- Already have SA: `simcash-editor@simcash-487714.iam.gserviceaccount.com`
- Need: `Vertex AI User` role on the SA
- Cloud Run: SA credentials auto-available via metadata server
- Local dev: `GOOGLE_APPLICATION_CREDENTIALS` already set

#### 6. Cloud Run Env
- Add `SIMCASH_DEFAULT_MODEL=google-vertex:gemini-3.0-pro` to deploy command
- No API key needed for Vertex AI (uses SA auth)

## Implementation Order
1. Grant Vertex AI User role to SA
2. Backend: `settings.py` + endpoints + tests
3. Backend: Wire `streaming_optimizer.py` to use settings
4. Frontend: Admin dashboard model selector
5. Test with Gemini 3 Pro end-to-end
6. Deploy

## Testing
- Unit tests for settings CRUD (mock Firestore)
- Unit test for LLMConfig with google-vertex provider
- Integration test: verify Gemini 3 Pro streaming works (manual)

## Risk
- Gemini 3 Pro may not follow the policy JSON schema as reliably as GPT-5.2
- Need to test prompt compatibility across providers
- Vertex AI quotas may differ from OpenAI
