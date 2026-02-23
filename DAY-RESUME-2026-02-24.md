# DAY-24 Resume — 2026-02-24

## What Was Done Today

### Per-Agent Model Routing via LiteLLM Admin UI

Full implementation of dynamic, per-agent LLM model selection managed from the MedusaJS admin UI. This replaces hardcoded env vars with database-driven model configuration, adds fallback model support, and enables cross-service config sharing.

---

### 1. Schema Changes (MedusaJS AI Agent Module)

**AI Agent model** (`modules/ai-agent/models/ai-agent.ts`):
- Added `fallback_model_name` — text, nullable (e.g., `"gemini-2.0-flash"`)
- Added `requires_grounding` — boolean, default `false` (when true, pricing service calls Gemini directly with Google Search tool instead of LiteLLM)
- Added `supplier_search` and `price_search` to agent_type enum

**Execution Log model** (`modules/ai-agent/models/ai-execution-log.ts`):
- Added `fallback_used` — boolean, default `false`
- Added `fallback_model` — text, nullable

**Constants** (`modules/ai-agent/constants.ts`):
- Added `"supplier_search"` and `"price_search"` to `AGENT_TYPES` array

**Migration** (`migrations/Migration20260223230118.ts`):
- Uses `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (NOT `CREATE TABLE IF NOT EXISTS`)
- Updates `ai_agent_agent_type_check` constraint to include new types
- Successfully run against MedusaJS DB (port 5434)

### 2. Backend Service Fallback Logic

**Service** (`modules/ai-agent/service.ts`):
- Refactored `executeLLMAgent()` with inner `callLLM(modelName)` function
- Try primary model → catch → if `fallback_model_name` set, retry with fallback
- `executeAgent()` logs `fallback_used` and `fallback_model` to execution log
- Added default system/user prompts for `supplier_search` and `price_search` types
- Updated `AgentType` union type with new types

### 3. Validators + Internal Config Endpoint

**Validators** (`api/admin/ai-agents/validators.ts`):
- Added `fallback_model_name: z.string().optional().nullable()` to create/update schemas
- Added `requires_grounding: z.boolean().optional()` to create/update schemas

**Middleware** (`api/admin/ai-agents/middlewares.ts`):
- Added auth bypass for internal endpoint using `allowUnauthenticated: true`

**Internal Config Endpoint** (`api/admin/ai-agents/internal/config/route.ts`) — **NEW**:
- `GET /admin/ai-agents/internal/config`
- Auth: `x-internal-api-key` header validated against `INTERNAL_API_KEY` env var
- Returns all active agents keyed by `agent_type` with model configs
- Used by pricing service to dynamically select models

### 4. Admin UI Changes

**Agent Form Modal** (`agent-form-modal.tsx`):
- Added Fallback Model dropdown (filters out primary model from options)
- Added "Requires Grounding" checkbox with tooltip
- Added `supplier_search` and `price_search` to agent type selector with default prompts
- Fallback/grounding values auto-populate when editing existing agents

**Agents Tab** (`agents-tab.tsx`):
- New type colors: `supplier_search` → Green, `price_search` → Orange
- Shows fallback chain (e.g., "gpt-4o → gemini-2.0-flash") on agent cards
- Shows "Grounding" badge when `requires_grounding` is true

**Execution Logs Modal** (`execution-logs-modal.tsx`):
- Orange "FB" badge in table rows when `fallback_used` is true
- Amber detail panel showing which fallback model was used

### 5. Pricing Service Integration

**Agent Config Service** (`agent-config.service.ts`) — **NEW**:
- Singleton fetching per-agent model configs from MedusaJS admin API
- Redis cache with 5-minute TTL (key: `agent-config:all`)
- Methods: `fetchAgentConfigs()`, `getAgentConfig(agentType)`, `getModelName(agentType)`
- Falls back to `LITELLM_MODEL` env var when MedusaJS unreachable

**Config** (`config/index.ts`):
- Added `MEDUSA_ADMIN_URL` (default: `http://klapp-marketplace:9000`)
- Added `INTERNAL_API_KEY` (optional, for auth)

**Tiered Search** (`tiered-search.service.ts`):
- `searchSuppliersWithLLM()` now fetches `supplier_search` agent config for dynamic model
- `searchWithLLM()` checks `requires_grounding` flag → routes to Gemini direct vs LiteLLM
- Fallback retry: if primary model fails and `fallback_model_name` is set, retries

**Docker Compose** (`docker-compose.yml`):
- Added `MEDUSA_ADMIN_URL=http://klapp-marketplace:9000` to pricing service
- Added `INTERNAL_API_KEY=${INTERNAL_API_KEY}` to pricing service

### 6. Seed Default Agents

**Seed script** (`scripts/seed-ai-agents.ts`) — **NEW**:
- Idempotent — creates new agents, updates existing ones with fallback/grounding fields
- Uses `aiAgentModule.updateAIAgents([{ id, ...data }])` format (array of objects)
- Run with: `npx medusa exec ./src/scripts/seed-ai-agents.ts`

**Default agent configurations seeded:**

| Agent Type | Primary Model | Fallback | Grounding | Temp |
|------------|--------------|----------|-----------|------|
| `email_parser` | `gpt-4o` | `gemini-2.0-flash` | No | 0.3 |
| `rfq_classifier` | `gemini-2.0-flash` | `gpt-4o-mini` | No | 0.5 |
| `supplier_matcher` | `gpt-4o` | `gemini-2.0-flash` | No | 0.7 |
| `quote_analyzer` | `gpt-4o` | `gemini-2.0-flash` | No | 0.6 |
| `supplier_search` | `gpt-4o` | `gemini-2.0-flash` | No | 0.1 |
| `price_search` | `gemini-2.0-flash` | null | **Yes** | 0.1 |

**Result:** 4 existing agents updated, 2 new agents created (supplier_search, price_search)

---

## Commits

### klapp-marketplace (`8a763ab`)
```
feat: add per-agent model routing with fallback support
```
**13 files changed** (+462/-52):
- `backend/src/admin/routes/ai-agents/components/agent-form-modal.tsx`
- `backend/src/admin/routes/ai-agents/components/agents-tab.tsx`
- `backend/src/admin/routes/ai-agents/components/execution-logs-modal.tsx`
- `backend/src/api/admin/ai-agents/internal/config/route.ts` (NEW)
- `backend/src/api/admin/ai-agents/middlewares.ts`
- `backend/src/api/admin/ai-agents/validators.ts`
- `backend/src/modules/ai-agent/constants.ts`
- `backend/src/modules/ai-agent/migrations/Migration20260223230118.ts` (NEW)
- `backend/src/modules/ai-agent/models/ai-agent.ts`
- `backend/src/modules/ai-agent/models/ai-execution-log.ts`
- `backend/src/modules/ai-agent/service.ts`
- `backend/src/scripts/seed-ai-agents.ts` (NEW)
- `backend/src/scripts/seed-all-ai_and_quote_modules.ts`

### klapp-supplier-discovery (`778e837`)
```
feat: integrate dynamic agent config from MedusaJS for model selection
```
**3 files changed** (+394/-551):
- `services/klapp-pricing-service/src/config/index.ts`
- `services/klapp-pricing-service/src/services/agent-config.service.ts` (NEW)
- `services/klapp-pricing-service/src/services/tiered-search.service.ts`

### klapp-ai-agent-rfq (`d95b992`)
```
feat: add MEDUSA_ADMIN_URL and INTERNAL_API_KEY env vars for pricing service
```
**1 file changed** (+12/-6):
- `docker/compose/docker-compose.yml`

---

## Bug Fix: Import Path Error

**Problem:** `Cannot find module '../../../../modules/ai-agent'` when starting MedusaJS
**Root cause:** Route at `api/admin/ai-agents/internal/config/route.ts` is 5 directories deep from `src/`, not 4
**Fix:** Changed import from `../../../../modules/ai-agent` to `../../../../../modules/ai-agent`
**Status:** Fixed and included in the commit

---

## Session 2: RFQ-2026-00082 Root Cause Investigation & Fix

### MedusaJS Admin UI Verification
- MedusaJS starts without errors on port 9000 (import path fix from earlier commit works)
- Admin API accessible and authenticated

### RFQ-2026-00082 Issues Found & Fixed

**Issue 1: Customer data empty in MedusaJS**
- Directly patched MedusaJS DB: customer_name="Muhammad Usman", customer_company="Al-Usman Traders", customer_email=NULL (no real customer email available), priority="urgent"

**Issue 2: from_email = rfq@klapp.ai (SYSTEMIC — 63/82 RFQs = 77%)**
- **Root Cause**: Hostinger mail server auto-forwards rfq@klapp.ai → Gmail inbox (klappai.local@gmail.com). The forwarding rewrites the From header to rfq@klapp.ai, losing the original sender's email.
- All forwarded emails have `message_id` ending in `@klapp.ai` (not the original sender's mail server)
- The original sender's email is NOT preserved in headers, body text, or anywhere extractable
- **Code fixes applied** (see files changed below)

**Issue 3: Title "t" prefix — "tInquiry for Grundfos..."**
- **Root Cause**: Same mail forwarding issue — Hostinger adds MIME encoding artifacts to Subject header during forwarding
- Other affected RFQs: RFQ-2026-00060 ("tRGHZ"), RFQ-2026-00068 ("ttaRGHZ")
- Only 3 out of 82 RFQs affected
- Data manually fixed in DB, no code fix applied (subject sanitization heuristic too risky)

**Issue 4: Priority downgraded urgent → medium**
- Priority mapping code is correct (`"urgent": "urgent"`)
- Issue: Kafka Phase 1 event from email-processing-service didn't carry priority field
- rfq-sync-subscriber.ts defaults to "medium" when priority is missing

### Code Changes (Not Yet Committed)

**`klapp-email-processing-service/src/api/main.py`**:
- Added `_OWN_EMAILS` and `_OWN_DOMAINS` sets + `_is_own_email()` helper
- CustomerInfo now filters out @klapp.ai domain emails — won't store own email as customer email
- Fixed resync endpoint (line 2070): changed email precedence from `source_email || customer_email` to `customer_email || from_email || source_email`

**`klapp-email-processing-service/src/services/storage/database_service.py`**:
- Added `from_email`, `parsed_data` columns to resync query
- Added `COALESCE(parsed_data->'customer'->>'name', c.name)` for better customer_name resolution

**`klapp-rfq-sync-service/src/syncers/rfq_syncer.py`**:
- Added `_own_domains` set + `_is_own()` helper for domain-based filtering
- Added `.lower()` to all email comparisons in the filter chain
- Fixed last-resort fallback: `source_email` now also filtered against own emails (was passing through rfq@klapp.ai)

---

## Pending Tasks for Tomorrow (Priority Order)

### 1. CRITICAL: Configure Hostinger Email Forwarding
The root cause of customer email loss and subject corruption is the Hostinger mail server.
- **Option A** (Best): Set up direct IMAP monitoring of rfq@klapp.ai on Hostinger — bypass Gmail forwarding entirely
  - Update n8n IMAP credential to point to Hostinger IMAP server
  - Remove the auto-forwarding rule
- **Option B**: Configure Hostinger to use "redirect" (alias) forwarding instead of "resend" mode
  - Preserves original From header and Subject encoding
- **Option C**: Add `X-Original-From` header in Hostinger forwarding rules, parse in n8n workflow

### 2. Commit & Push Code Fixes
```bash
# email-processing-service
cd klapp-email-processing-service
git add src/api/main.py src/services/storage/database_service.py
git commit -m "fix: prevent own @klapp.ai emails from being stored as customer email"
git push gitlab main

# rfq-sync-service
cd klapp-rfq-sync-service
git add src/syncers/rfq_syncer.py
git commit -m "fix: domain-based own-email filtering in customer email resolution"
git push gitlab main
```

### 3. Verify Admin UI Starts Without Errors
- Start MedusaJS: `cd klapp-marketplace/backend && npx medusa develop`
- Navigate to AI Agents tab → verify new agent types visible
- Check fallback dropdown and grounding checkbox work

### 4. Test Internal Config Endpoint
```bash
curl -H "x-internal-api-key: YOUR_KEY" http://localhost:9000/admin/ai-agents/internal/config
```

### 5. Test Fallback Mechanism
- Set an agent's primary model to invalid → verify fallback triggers
- Check execution log for `fallback_used: true`

### 6. Docker Rebuild & Test
```bash
cd klapp-ai-agent-rfq/docker/compose
docker compose build klapp-pricing-service klapp-email-processor klapp-rfq-sync-service
docker compose up -d
```

### 7. Outstanding Issues from Previous Days
- Run `migrations/006_communication_tracking.sql` on `klapp_ai_procurement` DB
- Add supplier confidence tags in Line Items tab UI

---

## Architecture Reference

### Data Flow: Admin UI → LLM Call

```
Admin UI (agent-form-modal.tsx)
    │ POST /admin/ai-agents
    ▼
MedusaJS Backend (service.ts)
    │ Stores in PostgreSQL (port 5434)
    ▼
ai_agent table
    │ Queried by internal API
    ▼
GET /admin/ai-agents/internal/config (route.ts)
    │ x-internal-api-key auth
    ▼
Pricing Service (agent-config.service.ts)
    │ Redis cache (5-min TTL)
    ▼
Tiered Search (tiered-search.service.ts)
    │ Check requires_grounding flag
    ├── false → LiteLLM proxy → configured provider
    └── true  → Gemini direct with Google Search tool
    │
    │ If primary fails and fallback configured:
    └── Retry with fallback_model_name
```

### Fallback Chain

```
Primary: agent.model_name via LiteLLM
    ↓ (on failure)
Fallback: agent.fallback_model_name via LiteLLM
    ↓ (on failure)
Error: logged to ai_execution_log with status=failed
```

### Environment Variables Required

```env
# MedusaJS (.env)
INTERNAL_API_KEY=some-secret-key    # For internal API auth

# Pricing Service (docker-compose.yml)
MEDUSA_ADMIN_URL=http://klapp-marketplace:9000
INTERNAL_API_KEY=${INTERNAL_API_KEY}
LITELLM_API_URL=http://litellm:4000  # Existing
LITELLM_API_KEY=${LITELLM_MASTER_KEY}  # Existing
GEMINI_API_KEY=${GOOGLE_API_KEY}     # For grounding calls
```
