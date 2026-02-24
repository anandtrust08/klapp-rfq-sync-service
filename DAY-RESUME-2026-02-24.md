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

**Internal Config Endpoint** — **RELOCATED** in Session 3:
- Moved from `api/admin/ai-agents/internal/config/route.ts` to `api/internal/ai-agents/config/route.ts`
- `GET /internal/ai-agents/config` (outside `/admin/` scope)
- Auth: `x-internal-api-key` header validated against `INTERNAL_API_KEY` env var
- Returns all active agents keyed by `agent_type` with model configs

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

### 6. Seed Default Agents

**Seed script** (`scripts/seed-ai-agents.ts`) — **NEW**:
- Idempotent — creates new agents, updates existing ones with fallback/grounding fields
- Run with: `npx medusa exec ./src/scripts/seed-ai-agents.ts`

| Agent Type | Primary Model | Fallback | Grounding | Temp |
|------------|--------------|----------|-----------|------|
| `email_parser` | `gpt-4o` | `gemini-2.0-flash` | No | 0.3 |
| `rfq_classifier` | `gemini-2.0-flash` | `gpt-4o-mini` | No | 0.5 |
| `supplier_matcher` | `gpt-4o` | `gemini-2.0-flash` | No | 0.7 |
| `quote_analyzer` | `gpt-4o` | `gemini-2.0-flash` | No | 0.6 |
| `supplier_search` | `gpt-4o` | `gemini-2.0-flash` | No | 0.1 |
| `price_search` | `gemini-2.0-flash` | null | **Yes** | 0.1 |

---

## Session 2: RFQ-2026-00082 Root Cause Investigation & Fix

### RFQ-2026-00082 Issues Found & Fixed

**Issue 1: Customer data empty in MedusaJS** — Patched directly in DB

**Issue 2: from_email = rfq@klapp.ai (SYSTEMIC — 63/82 RFQs = 77%)**
- Root Cause: Hostinger mail forwarding rewrites From header
- Code fixes applied to email-processing-service and rfq-sync-service

**Issue 3: Title "t" prefix** — Hostinger MIME encoding artifacts, manually fixed

**Issue 4: Priority downgraded** — Kafka event missing priority field

---

## Session 3: Completed Work (2026-02-24 afternoon)

### Task 1: Push Unpushed Commits — DONE
- `klapp-email-processing-service` → gitlab main
- `klapp-rfq-sync-service` → origin main

### Task 2: Internal Config Endpoint Fix — DONE

**Problem:** `GET /admin/ai-agents/internal/config` returns 401 even with correct API key. MedusaJS v2.9.0 applies default admin session auth to ALL `/admin/*` routes before custom middleware.

**Fix:** Relocated endpoint to `/internal/ai-agents/config` (outside `/admin/` scope).

**Auth tests PASSED:**
- No API key → 401
- Wrong API key → 401
- Correct API key → 200 (all 6 agents returned)

### Task 3: Docker Rebuild — DONE

**TS build failures fixed:**
- Removed unused `lastFetchError` property and references
- Removed unused `AgentConfig` type import
- Removed unused `supplierAgentConfig` variable

All 3 services built and running: `klapp-email-processor`, `rfq-sync-service`, `klapp-pricing-service`

### Task 4: Email Pipeline — IMAP Reconfiguration — DONE

**Key discovery:** The RFQ intake email is `commercial@ecorporates.com` (Google Workspace), NOT `rfq@klapp.ai` (Hostinger). Configured in MedusaJS Admin UI at `/app/settings/platform-settings`.

**Email architecture:**
| Direction | Email | Service |
|-----------|-------|---------|
| **Inbound** (IMAP monitoring) | `commercial@ecorporates.com` | Google Workspace (`imap.gmail.com:993`) |
| **Outbound** (auto-replies, quotes) | `rfq@klapp.ai` | Resend API |

**What was done:**
1. Created `scripts/setup-n8n-imap.sh` — provisions n8n IMAP credential via REST API
2. Fixed script auth: n8n v2 uses session login (`emailOrLdapLoginId`), not basic auth
3. Initially configured Hostinger IMAP for `rfq@klapp.ai` (wrong inbox)
4. Reconfigured to Google Workspace IMAP for `commercial@ecorporates.com` (correct intake)
5. n8n credential: `eCorporates IMAP - commercial@ecorporates.com` (ID: `UMCY4kid8DPi7uRe`)

**End-to-end pipeline test PASSED:**
```
rfq@klapp.ai → commercial@ecorporates.com (via SMTP)
    → Google Workspace inbox
    → n8n IMAP trigger (Email Gateway V2)
    → Kafka email.raw.received
    → Email Classifier (classified as RFQ)
    → Classification Bridge → Email Processor → DB
    → RFQ Sync → MedusaJS DB
    → Visible in MedusaJS Admin UI (/app/rfqs)
```
Test RFQ: `RFQ-154751: Siemens Industrial Ethernet Switch and PLC` — status `received`, sync_status `completed`

### Task 5: MedusaJS Admin UI Verification — DONE
- MedusaJS starts on port 9000, all 6 agents visible
- `INTERNAL_API_KEY` added to both MedusaJS and pricing service `.env`

---

## All Commits Today

### klapp-ai-agent-rfq (3 commits → pushed)
| Commit | Description |
|--------|-------------|
| `f25e4e9` | feat: add Hostinger direct IMAP configuration and setup script |
| `7d52e55` | fix: update IMAP setup script auth and export gateway workflow |
| `e061d7a` | feat: switch IMAP intake to commercial@ecorporates.com (Google Workspace) |

### klapp-marketplace (1 commit → pushed)
| Commit | Description |
|--------|-------------|
| `3cc87bb` | fix: move internal config endpoint outside /admin/ to bypass MedusaJS session auth |

### klapp-supplier-discovery (2 commits → pushed)
| Commit | Description |
|--------|-------------|
| `3e70d26` | fix: remove unused TypeScript variables in pricing service |
| `1f215e0` | fix: update internal config endpoint URL to /internal/ai-agents/config |

---

## Pending Tasks for Tomorrow (Priority Order)

### 1. Test Fallback Mechanism
- Set an agent's primary model to invalid → verify fallback triggers
- Check execution log for `fallback_used: true`

### 2. Google Search Grounding Test
- Send an RFQ with a real part number to `commercial@ecorporates.com`
- Verify `price_search` agent (requires_grounding=true) calls Gemini with Google Search tool
- Confirm pricing data appears in MedusaJS Admin UI

### 3. Make IMAP Config Dynamic from Platform Settings
- Currently n8n IMAP credential is manually set
- Ideally `setup-n8n-imap.sh` should read intake email from MedusaJS platform settings API
- Low priority — current setup works, only changes if admin changes intake email

### 4. Outstanding Issues from Previous Days
- Run `migrations/006_communication_tracking.sql` on `klapp_ai_procurement` DB
- Add supplier confidence tags in Line Items tab UI

---

## Architecture Reference

### Email Pipeline Flow

```
Buyer sends RFQ to commercial@ecorporates.com
    │
    ▼
Google Workspace inbox (imap.gmail.com:993)
    │
    ▼
n8n Email Gateway V2 (IMAP trigger)
    │ Publishes to Kafka
    ▼
email.raw.received → Email Classifier → email.classified.rfq
    │
    ▼
Classification Bridge (W10) → Email Processor → DB
    │
    ▼
rfq.created → RFQ Sync Service → MedusaJS Admin UI (/app/rfqs)
```

### Internal Config Flow

```
MedusaJS Admin UI → ai_agent table (port 5434)
    │
    ▼
GET /internal/ai-agents/config (x-internal-api-key auth)
    │ (outside /admin/ scope — no session auth required)
    ▼
Pricing Service (agent-config.service.ts)
    │ Redis cache (5-min TTL)
    │
    ├── requires_grounding=false → LiteLLM → configured model
    └── requires_grounding=true  → Gemini Direct API (Google Search tool)
    │
    │ If primary fails and fallback configured:
    └── Retry with fallback_model_name
```

### Environment Variables

```env
# MedusaJS (.env)
INTERNAL_API_KEY=klapp-internal-api-key-dev-2026

# Pricing Service (docker-compose.yml)
MEDUSA_ADMIN_URL=http://klapp-marketplace:9000
INTERNAL_API_KEY=${INTERNAL_API_KEY}

# n8n IMAP — intake reads from commercial@ecorporates.com (Google Workspace)
# Configured via n8n credential: "eCorporates IMAP - commercial@ecorporates.com"
# IMAP server: imap.gmail.com:993 (App Password auth)

# Outbound emails via Resend (sends from rfq@klapp.ai)
RESEND_API_KEY=re_Uyw5UQuz_...
```
