# LLM Model Switching — Development Plan

**Status**: In Progress
**Date**: 2026-02-18
**Branch**: feature/interactive-web-sandbox

## Goal
Make the optimization model admin-switchable (Gemini 3 Pro via Vertex AI as primary, GPT-5.2 as fallback), stored in Firestore, selectable from the admin dashboard.

## Web Invariants
- **WEB-INV-1 (Policy Reality)**: Model change doesn't affect policy execution — only the LLM that proposes policies changes
- **WEB-INV-2 (Agent Isolation)**: Unchanged — isolation is in the prompt, not the model
- **WEB-INV-5 (Auth Gate)**: Settings endpoints are admin-only

## Files

### New
| File | Purpose |
|------|---------|
| `web/backend/app/settings.py` | Platform settings CRUD (Firestore-backed, cached) |
| `web/backend/tests/test_settings.py` | Settings unit tests |

### Modified
| File | Changes |
|------|---------|
| `web/backend/app/streaming_optimizer.py` | Use `get_llm_config()` instead of hardcoded model |
| `web/backend/app/main.py` | Add settings router |
| `web/frontend/src/components/AdminDashboard.tsx` | Add model selector section |
| `web/frontend/src/api.ts` | Add settings API functions |

### NOT Modified
| File | Why |
|------|-----|
| `api/payment_simulator/llm/config.py` | Already supports all providers — import only |
| `simulator/` | Never touch the engine |

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | IAM + Backend settings module + endpoints | 1h | 12 tests |
| 2 | Wire optimizer + frontend model selector | 1h | 4 tests |
| 3 | E2E test with Gemini 3 Pro | 30m | Manual |
| 4 | Deploy | 30m | Verify live |

## Phase 1: Backend Settings

### IAM
- Grant `Vertex AI User` role to SA `simcash-editor@simcash-487714.iam.gserviceaccount.com`

### Backend: `web/backend/app/settings.py`
- `PlatformSettings` dataclass: `optimization_model`, `model_settings`, `available_models`
- `SettingsManager` class:
  - `get_settings()` → Firestore read with 60s TTL cache
  - `update_settings(updates: dict, admin_email: str)` → Firestore write, invalidate cache
  - `get_llm_config()` → build `LLMConfig` from current settings
- Default model: `SIMCASH_DEFAULT_MODEL` env var or `"openai:gpt-5.2"`
- Local dev (no Firestore): return defaults from env

### Backend: endpoints in `main.py`
- `GET /api/settings` (admin) → current settings
- `PATCH /api/settings` (admin) → update settings
- `GET /api/settings/models` (any auth'd user) → available models

### Tests: `test_settings.py`
- Settings defaults without Firestore
- Settings CRUD with mock Firestore
- `get_llm_config()` for each provider (openai, google-vertex, anthropic)
- Auth gate on settings endpoints

## Phase 2: Wiring + Frontend

### Backend: `streaming_optimizer.py`
- Import `settings_manager.get_llm_config()` 
- Replace hardcoded `LLMConfig(model="openai:gpt-5.2", ...)` with dynamic config
- Add model name to streaming events so frontend shows which model is reasoning

### Frontend: `AdminDashboard.tsx`
- "Optimization Model" section with dropdown
- Each option shows provider badge (Google/OpenAI/Anthropic)
- Current model highlighted
- Save button → `PATCH /api/settings`
- Success/error toast

### Frontend: Game UI
- Small badge in GameView showing active model name

## Success Criteria
1. Admin can switch model from dashboard
2. Next game optimization uses the selected model
3. Gemini 3 Pro produces valid policies via Vertex AI
4. GPT-5.2 still works as fallback
5. All tests pass
