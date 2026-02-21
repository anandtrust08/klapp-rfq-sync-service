# DAY: Deploy LiteLLM Step B — Service Routing + E2E Testing

**Date**: 2026-02-22
**Previous session**: Step B code committed and pushed to GitLab
**Goal**: Deploy LiteLLM routing to VPS, test end-to-end, validate admin UI, verify per-service model management

---

## Context: What Was Done (Step B Implementation)

### Commits Pushed
| Repo | Commit | Description |
|------|--------|-------------|
| `klapp-email-processing-service` | `e76d22f` | `feat: add LiteLLM gateway support for centralized LLM routing (Step B)` |
| `klapp-ai-agent-rfq` | `3125e0b` | `feat: wire services to LiteLLM gateway env vars (Step B)` |

### Code Changes Summary

**klapp-email-processing-service** (3 files):
1. **`src/config.py`** — Added `LITELLM_API_URL`, `LITELLM_API_KEY`, `LITELLM_MODEL` settings. Updated `LLM_PROVIDER` to accept `"litellm"`. Added production validation and debug logging for litellm.
2. **`src/services/llm/gateway.py`** — Added `LiteLLMClient(BaseLLMClient)` class using aiohttp to call LiteLLM's OpenAI-compatible `/v1/chat/completions` endpoint. Integrated into `LLMGateway` singleton: `_detect_provider()`, `_detect_available_providers()`, `_create_client()`, `FALLBACK_ORDER = ["litellm", "gemini", "anthropic", "ollama"]`.
3. **`src/services/classification/ai_classifier.py`** — Added `_call_litellm()` method. When `LLM_PROVIDER=litellm`, classifier uses aiohttp+LiteLLM instead of `google.generativeai` SDK. Same JSON parsing/validation logic for both paths.

**klapp-ai-agent-rfq** (4 files):
1. **`docker-compose.yml`** (dev) — Added `LITELLM_API_URL=http://litellm:4000`, `LITELLM_API_KEY=${LITELLM_MASTER_KEY}`, `LITELLM_MODEL=${GEMINI_MODEL:-gemini-2.0-flash}` + `depends_on: litellm` to: email-processor, ai-agent, email-consumer, email-classifier, enrichment-service, pricing-service.
2. **`docker-compose.prod.yml`** — Same additions for: email-processor, email-consumer, enrichment-service, pricing-service.
3. **`.env.example`** — Clarified that `LITELLM_MASTER_KEY` is reused as `LITELLM_API_KEY`.
4. **`README.md`** — Updated LiteLLM status to Step B.

### What This Does NOT Change
- Default `LLM_PROVIDER` remains `gemini` — litellm is opt-in
- No Kafka topic changes, no DB schema changes, no n8n workflow changes
- Enrichment-service and pricing-service have env vars wired but still need **code changes** (Step C) to actually route through LiteLLM
- Medusa `llm-service.ts` still calls providers directly (separate migration)

### Rollback
Set `LLM_PROVIDER=gemini` in `.env` or per-service docker-compose environment. Restart affected containers.

---

## PART 1: VPS Deployment

### Task 1.1: Pull Latest Code on VPS
```bash
ssh root@82.29.178.249
cd /opt/klapp/klapp-ai-agent-rfq
git pull gitlab main  # Should show 769571c..3125e0b

cd /opt/klapp/klapp-email-processing-service
git pull gitlab main  # Should show 4c500e3..e76d22f
```

### Task 1.2: Verify LiteLLM Database Exists
Step A created the `klapp_litellm` database. Verify:
```bash
docker exec medusa_postgres psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'klapp_litellm'"
```
If missing, run the db-init profile:
```bash
cd /opt/klapp/klapp-ai-agent-rfq/docker/compose
docker compose -f docker-compose.prod.yml --profile init up db-init
```

### Task 1.3: Verify .env Has LiteLLM Keys
```bash
cd /opt/klapp/klapp-ai-agent-rfq/docker/compose
grep LITELLM .env
```
Expected:
```
LITELLM_MASTER_KEY=sk-<actual-key>
LITELLM_SALT_KEY=sk-<actual-key>
LITELLM_PORT=4000
```
If `LITELLM_MASTER_KEY` is still a placeholder, generate it:
```bash
echo "LITELLM_MASTER_KEY=sk-$(openssl rand -hex 32)" >> .env
echo "LITELLM_SALT_KEY=sk-$(openssl rand -hex 32)" >> .env
```

### Task 1.4: Deploy with LLM_PROVIDER=gemini First (Safe Start)
Keep `LLM_PROVIDER=gemini` in `.env` for initial deploy — this ensures everything works as before while LiteLLM starts up alongside:
```bash
cd /opt/klapp/klapp-ai-agent-rfq/docker/compose
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### Task 1.5: Verify LiteLLM Is Healthy
```bash
# Health check
docker exec klapp-litellm curl -s http://localhost:4000/health/readiness
# Expected: {"status":"healthy"}

# List available models
docker exec klapp-litellm curl -s http://localhost:4000/v1/models \
  -H "Authorization: Bearer $(grep LITELLM_MASTER_KEY .env | cut -d= -f2)"

# Check logs for errors
docker logs klapp-litellm --tail 20
```

### Task 1.6: Test LiteLLM API Directly
```bash
LITELLM_KEY=$(grep LITELLM_MASTER_KEY .env | cut -d= -f2)

# Test Gemini through LiteLLM
curl -s http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -d '{"model":"gemini-2.0-flash","messages":[{"role":"user","content":"Reply with just: hello"}],"max_tokens":10}' | jq .
```
Expected: A valid OpenAI-format response with `choices[0].message.content`.

### Task 1.7: Switch to LiteLLM Provider
Once LiteLLM is confirmed healthy:
```bash
# Edit .env
sed -i 's/LLM_PROVIDER=gemini/LLM_PROVIDER=litellm/' .env

# Recreate email-processing services only
docker compose -f docker-compose.prod.yml up -d --force-recreate \
  email-processor email-consumer
```

### Task 1.8: Verify Services Started with LiteLLM
```bash
# email-processor should log "LiteLLMClient initialized"
docker logs klapp-email-processor 2>&1 | grep -i litellm

# email-consumer should log similar
docker logs klapp-email-consumer 2>&1 | grep -i litellm
```

---

## PART 2: End-to-End Email Pipeline Test

### Task 2.1: Send Test RFQ Email
Send a test RFQ email to `rfq@klapp.ai` (or the configured inbox). Include:
- Subject: "RFQ - Test LiteLLM Routing - 50 Hydraulic Cylinders"
- Body with buyer info, line items, delivery details
- Optionally attach a PDF

### Task 2.2: Verify Email Classification (ai_classifier.py → LiteLLM)
```bash
# Watch classifier logs
docker logs -f klapp-email-processor 2>&1 | grep -i "classif"
```
Expected: `AI classified email: type=rfq, party=CUSTOMER, confidence=0.xx`
Should NOT show any `google.generativeai` errors. Should show LiteLLM being called.

### Task 2.3: Verify RFQ Extraction (gateway.py → LiteLLMClient)
```bash
# Watch extraction logs
docker logs -f klapp-email-processor 2>&1 | grep -i "extract\|LLM\|litellm"
```
Expected: `LiteLLMClient initialized`, `Sending X char prompt to litellm`, `Extraction successful. Quality: X.XX, Provider: litellm`

### Task 2.4: Verify LiteLLM Received the Requests
```bash
docker logs -f klapp-litellm 2>&1 | grep -i "POST\|request\|gemini"
```
Should show incoming requests from email-processor hitting the `/v1/chat/completions` endpoint.

### Task 2.5: Verify RFQ Stored in Database
```bash
docker exec medusa_postgres psql -U postgres -d klapp_ai_procurement \
  -c "SELECT id, subject, email_type, classification_confidence, created_at FROM rfqs ORDER BY created_at DESC LIMIT 3;"
```

### Task 2.6: Verify Kafka Event Produced
```bash
# Check rfq.created topic
docker exec klapp-kafka-broker kafka-console-consumer \
  --bootstrap-server localhost:29092 \
  --topic rfq.created \
  --from-beginning --max-messages 3 --timeout-ms 5000
```

### Task 2.7: Verify RFQ Synced to MedusaJS
```bash
docker exec medusa_postgres psql -U postgres -d klapp-backend \
  -c "SELECT id, title, status, created_at FROM rfq ORDER BY created_at DESC LIMIT 3;"
```

---

## PART 3: LiteLLM Admin UI — Real-Time Monitoring

### Task 3.1: Access LiteLLM Admin Dashboard
- **URL**: `https://llm.klapp.ai` (production, requires admin basic auth)
- **Login**: Username: `admin`, Password: value of `LITELLM_MASTER_KEY`
- Alternatively on VPS directly: `http://localhost:4000/ui`

### Task 3.2: Verify Models Are Listed
Navigate to **Models** tab. Should see:
- `gemini-2.0-flash` (active — primary)
- `gemini-1.5-flash` (active — fallback)
- `claude-3.5-sonnet` (inactive unless ANTHROPIC_API_KEY set)
- `gpt-4o` / `gpt-4o-mini` (inactive unless OPENAI_API_KEY set)
- `llama3.1` (inactive on VPS — no local Ollama)

### Task 3.3: Monitor Real-Time Request Logs
1. Go to **Logs** or **Usage** tab in LiteLLM UI
2. Send another test email to trigger LLM calls
3. Verify you can see:
   - Request timestamp
   - Model used (e.g., `gemini/gemini-2.0-flash`)
   - Input/output tokens
   - Latency (response time)
   - Cost per request
   - Success/failure status

### Task 3.4: Verify Cost Tracking
After processing a few emails:
1. Check **Usage** tab — should show token counts and estimated cost
2. Verify cost breakdown per model
3. Note: LiteLLM tracks cost automatically based on model pricing tables

### Task 3.5: Check Fallback Routing
In LiteLLM UI, verify router settings show:
- `gemini-2.0-flash` → fallback to `gemini-1.5-flash` → `llama3.1`
- `gemini-1.5-flash` → fallback to `llama3.1`

---

## PART 4: Per-Service Model Management

### Task 4.1: Test Per-Service Model Override
The goal: Run supplier matching on GPT-4o while everything else uses Gemini.

**Option A — Via LiteLLM Config (Recommended)**
LiteLLM supports adding models via the Admin UI:
1. Go to LiteLLM UI → **Models** → **Add Model**
2. Add `gpt-4o` with your `OPENAI_API_KEY`
3. Test it works:
```bash
LITELLM_KEY=$(grep LITELLM_MASTER_KEY .env | cut -d= -f2)
curl -s http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Say hello"}],"max_tokens":10}' | jq .
```

**Option B — Per-Container Override**
To make only one service use a different model, override `LITELLM_MODEL` for that container:
```yaml
# In docker-compose.prod.yml, for a specific service:
environment:
  - LITELLM_MODEL=gpt-4o  # This service uses GPT-4o
  # Other services keep LITELLM_MODEL=gemini-2.0-flash
```

### Task 4.2: Verify Model Routing in LiteLLM Logs
After making a request with `model=gpt-4o`:
```bash
docker logs klapp-litellm 2>&1 | grep "gpt-4o"
```
Should show the request being routed to OpenAI.

### Task 4.3: Test Supplier Matching with GPT-4o Scenario
This is a **future** scenario (pricing-service needs Step C code changes). For now, verify the concept works by:
1. Calling LiteLLM directly with `model=gpt-4o` — confirm it works
2. Calling LiteLLM with `model=gemini-2.0-flash` — confirm it works
3. This proves that once pricing-service code is updated, you can route it to any model

### Task 4.4: Test Model Switching via Admin UI
1. In LiteLLM UI, disable a model (e.g., `gemini-1.5-flash`)
2. Verify it's no longer returned in `/v1/models` list
3. Re-enable it
4. This demonstrates admin-level model management without code deploys

---

## PART 5: Medusa Admin UI — AI Agents Page

### Task 5.1: Access AI Agents Page
- **URL**: `https://admin.klapp.ai/app/ai-agents`
- Login with admin credentials

### Task 5.2: Verify Agent List Loads
The page should display agent cards for:
| Agent | Type | Expected Provider |
|-------|------|-------------------|
| Email Parser | email_parser | gemini |
| RFQ Classifier | rfq_classifier | gemini |
| Supplier Matcher | supplier_matcher | gemini |
| Quote Analyzer | quote_analyzer | gemini |
| Sentiment Analyzer | sentiment_analyzer | gemini |
| Price Optimizer | price_optimizer | gemini |

Check each card shows: status, model, execution count, success rate, avg time, cost.

### Task 5.3: Verify Agent Stats API
```bash
curl -s https://admin.klapp.ai/admin/ai-agents/stats \
  -H "Authorization: Bearer <admin-token>" | jq .
```
Should return aggregate stats: total agents, total executions, avg success rate, total tokens, total cost.

### Task 5.4: Test Agent Execution
1. Click "Test" on the **Email Parser** agent
2. Input test data:
```json
{
  "entity_type": "rfq",
  "input_data": {
    "email_content": "Need 50 hydraulic cylinders, bore 40mm, stroke 200mm. Delivery to Hamburg, Germany. Budget EUR 15,000. Quote needed by March 1."
  }
}
```
3. Verify execution completes and shows:
   - Parsed output (JSON with line items, buyer, etc.)
   - Tokens used
   - Cost
   - Execution time

### Task 5.5: View Execution Logs
1. Click "Logs" on any agent
2. Verify historical executions are listed with timestamps, status, tokens, cost

### Task 5.6: Edit Agent Configuration
1. Click "Edit" on the **Supplier Matcher** agent
2. Verify you can change:
   - Model (e.g., from `gemini-2.0-flash` to `gpt-4o`)
   - Temperature
   - Confidence threshold
3. Save and verify the change persists

### Task 5.7: Verify Cost Tracking Accuracy
Compare costs shown in:
1. Medusa AI Agents page (per-agent cost)
2. LiteLLM Admin UI (per-model cost)
They should be consistent after processing the same requests.

**Note**: The Medusa `llm-service.ts` currently calls LLM providers directly (not through LiteLLM). The cost tracking on the AI Agents page uses its own pricing table in `llm-service.ts`. LiteLLM cost tracking is independent. Step C will unify these.

---

## PART 6: Rollback Verification

### Task 6.1: Test Rollback to Direct Gemini
```bash
# Switch back to gemini
sed -i 's/LLM_PROVIDER=litellm/LLM_PROVIDER=gemini/' .env
docker compose -f docker-compose.prod.yml up -d --force-recreate email-processor email-consumer
```

### Task 6.2: Verify Direct Gemini Works
```bash
docker logs klapp-email-processor 2>&1 | grep -i "gemini\|provider"
# Should show "GeminiClient initialized" — NOT LiteLLMClient
```

### Task 6.3: Send Another Test Email
Verify the full pipeline still works with direct Gemini calls (no LiteLLM in the path).

### Task 6.4: Switch Back to LiteLLM (If Tests Pass)
```bash
sed -i 's/LLM_PROVIDER=gemini/LLM_PROVIDER=litellm/' .env
docker compose -f docker-compose.prod.yml up -d --force-recreate email-processor email-consumer
```

---

## PART 7: Known Limitations & Next Steps (Step C)

### Services NOT Yet Routing Through LiteLLM (Code Changes Needed)

| Service | Issue | Fix Required |
|---------|-------|-------------|
| **klapp-enrichment-service** | Uses `@anthropic-ai/sdk` — no custom base URL support | Replace SDK with direct HTTP calls to LiteLLM's OpenAI-compatible endpoint |
| **klapp-pricing-service** (Gemini) | Uses custom `GeminiClient` with Gemini-native API format | Add OpenAI-compatible code path for LiteLLM |
| **klapp-pricing-service** (Anthropic) | Hard-coded `https://api.anthropic.com` | Extract base URL to config |
| **Medusa llm-service.ts** | Direct API calls to Gemini/OpenAI/Anthropic | Add LiteLLM provider option with configurable base URL |
| **n8n workflows (05, 10, 12)** | HTTP Request nodes call Gemini directly | Update n8n HTTP nodes to call LiteLLM endpoint |

### LiteLLM Config Models Available
From `litellm_config.yaml`:
```
gemini-2.0-flash    → gemini/gemini-2.0-flash (active)
gemini-1.5-flash    → gemini/gemini-1.5-flash (active, fallback)
claude-3.5-sonnet   → anthropic/claude-3-5-sonnet-20241022 (needs ANTHROPIC_API_KEY)
gpt-4o              → openai/gpt-4o (needs OPENAI_API_KEY)
gpt-4o-mini         → openai/gpt-4o-mini (needs OPENAI_API_KEY)
llama3.1            → ollama_chat/llama3.1:8b (local only)
```

### Fallback Chain (Configured in router_settings)
```
gemini-2.0-flash → gemini-1.5-flash → llama3.1
gemini-1.5-flash → llama3.1
```

---

## Quick Reference

| Item | Value |
|------|-------|
| LiteLLM internal URL | `http://litellm:4000` |
| LiteLLM external URL | `https://llm.klapp.ai` |
| LiteLLM Admin UI | `https://llm.klapp.ai/ui` (or `http://localhost:4000/ui` on VPS) |
| Admin login | `admin` / `$LITELLM_MASTER_KEY` |
| Health check | `http://localhost:4000/health/readiness` |
| Models endpoint | `http://localhost:4000/v1/models` |
| Chat endpoint | `http://localhost:4000/v1/chat/completions` |
| Activate LiteLLM | `LLM_PROVIDER=litellm` in `.env` |
| Rollback | `LLM_PROVIDER=gemini` in `.env` |
| Medusa AI Agents | `https://admin.klapp.ai/app/ai-agents` |
