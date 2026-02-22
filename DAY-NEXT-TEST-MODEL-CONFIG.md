# Test & Deploy: Admin Model Configuration Tab + All Pending Tasks

**Created:** 2026-02-22
**Commits:** klapp-marketplace `3687aaa`, klapp-ai-agent-rfq `06c0831`
**Both pushed to GitLab:** Yes (2026-02-22)

---

## Task 1: Backend API Tests (Local)

### Pre-requisites
- [ ] LiteLLM container running with latest `litellm_config.yaml` (includes `store_model_in_db: true`)
- [ ] klapp-marketplace backend rebuilt with latest commit
- [ ] At least one API key available for testing (Gemini key should work — already configured)

```bash
# Rebuild LiteLLM with updated config
cd /path/to/klapp-ai-agent-rfq
docker compose -f docker/compose/docker-compose.yml up -d litellm --build

# Rebuild marketplace backend
cd /path/to/klapp-marketplace
docker compose up -d marketplace-backend --build

# Verify both running
docker compose ps | grep -E "litellm|marketplace"
```

### 1.1 List Model Configs (GET)
```bash
TOKEN="<admin-jwt>"

curl -s "localhost:9000/admin/ai-agents/models/config" \
  -H "Authorization: Bearer $TOKEN" | jq .
```
**Expected:** JSON with `configs` array (6 entries for YAML models) + `health` object
- [ ] Each config has `model_id`, `model_name`, `litellm_model`, `provider`, `healthy`, `db_model`
- [ ] `api_key_configured` is `true` for gemini models, `false` for openai/anthropic (no keys set)
- [ ] `db_model` is `false` for all (they're YAML-defined)
- [ ] `healthy` matches what LiteLLM `/health` reports

### 1.2 Add a Model (POST)
```bash
curl -X POST "localhost:9000/admin/ai-agents/models/config" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "gpt-4o-test",
    "provider": "openai",
    "litellm_model": "openai/gpt-4o",
    "api_key": "sk-test-key-here",
    "timeout": 120,
    "max_tokens": 8192
  }'
```
- [ ] Returns `{ "success": true }`
- [ ] Re-run GET — new model appears with `db_model: true`
- [ ] Omitting `api_key` for cloud provider returns 400 error

### 1.3 Test a Model (POST)
```bash
curl -X POST "localhost:9000/admin/ai-agents/models/config/test" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model_name": "gemini-2.0-flash"}'
```
- [ ] Healthy model returns `{ "success": true, "latency_ms": <number> }`
- [ ] Unhealthy model returns `{ "success": false, "error": "..." }`

### 1.4 Update a Model (POST)
```bash
curl -X POST "localhost:9000/admin/ai-agents/models/config/update" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model_id": "<model_id_from_GET>", "timeout": 180}'
```
- [ ] Returns `{ "success": true }`
- [ ] Re-run GET — timeout updated to 180

### 1.5 Delete a Model (POST)
```bash
curl -X POST "localhost:9000/admin/ai-agents/models/config/delete" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"id": "<model_id>"}'
```
- [ ] Model removed from GET listing
- [ ] YAML model reappears on next LiteLLM restart

### 1.6 Validation Tests
```bash
# Missing api_key for cloud provider → 400
curl -X POST "localhost:9000/admin/ai-agents/models/config" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model_name":"test","provider":"openai","litellm_model":"openai/test"}'

# Ollama without api_key → success
curl -X POST "localhost:9000/admin/ai-agents/models/config" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model_name":"test-llama","provider":"ollama","litellm_model":"ollama_chat/llama3.1:8b","api_base":"http://host.docker.internal:11434"}'
```

---

## Task 2: Frontend UI Tests (Local)

### 2.1 Configuration Tab Renders
- [ ] Navigate to `/app/ai-agents`
- [ ] Click "Configuration" tab (last tab)
- [ ] Summary cards show: Total Models, Healthy (green), Unhealthy (red), LiteLLM status
- [ ] Model cards render in 2-column grid
- [ ] Each card shows: model name, provider badge (colored), litellm model string, health badge, API key status, source badge (YAML/API)

### 2.2 Add Model Flow
- [ ] Click "Add Model" button
- [ ] Select provider "Google Gemini" — model dropdown shows gemini-2.0-flash, gemini-1.5-flash, gemini-1.5-pro
- [ ] Select provider "Ollama" — API key field hidden, API base pre-filled with `http://host.docker.internal:11434`
- [ ] Select provider "OpenAI" — API key field visible and required
- [ ] Click "Custom" — model dropdown replaced with free-text input
- [ ] Click "List" — returns to dropdown
- [ ] Click "Test" — shows green checkmark + latency (for healthy model) or red X + error
- [ ] Click "Add Model" with valid data — model appears in grid immediately

### 2.3 Edit Model Flow
- [ ] Click "Edit" on a model card
- [ ] Provider and model name are read-only
- [ ] API key field shows placeholder "API key configured (enter new to change)"
- [ ] Change timeout → click "Update Model" → card refreshes with new timeout

### 2.4 Delete Model Flow
- [ ] Click "Delete" on an API-added model → confirm dialog → model removed
- [ ] Click "Delete" on a YAML model → warning mentions "will reappear on restart" → model removed but returns after LiteLLM restart

### 2.5 Test Model Inline
- [ ] Click "Test" button on a model card
- [ ] Green result appears inline on the card with latency
- [ ] Test an unhealthy model — red result with error message

### 2.6 Auto-Refresh
- [ ] Leave tab open for 30+ seconds — data refreshes automatically
- [ ] Click "Refresh" button — manual refresh works

### 2.7 Agent Form Modal Integration
- [ ] Go to "Agents" tab → "Create Agent" or edit existing
- [ ] Model dropdown should show only healthy models
- [ ] If a model was added via Configuration tab, it appears in the agent model dropdown

---

## Task 3: Persistence Test (Local)

- [ ] Add a model via Configuration tab
- [ ] Restart LiteLLM container: `docker compose restart litellm`
- [ ] Wait for LiteLLM to come up
- [ ] Verify the API-added model is still present (check Configuration tab)
- [ ] This confirms `store_model_in_db: true` is working

---

## Task 4: VPS Deployment — All Services

### VPS Info
- **Server:** `82.29.178.249` (alias `klapp-vps`)
- **klapp-ai-agent-rfq path:** `/opt/klapp/klapp-ai-agent-rfq`
- **klapp-marketplace path:** `/opt/klapp/klapp-marketplace`
- **klapp-email-processing-service path:** `/opt/klapp/klapp-email-processing-service`
- **klapp-rfq-sync-service path:** `/opt/klapp/klapp-rfq-sync-service`
- **Docker network:** `klappnetwork`
- **Git remote name:** `gitlab` for all repos

### 4.1 Pull Latest Code on VPS
```bash
ssh root@82.29.178.249

# klapp-ai-agent-rfq (LiteLLM config + store_model_in_db)
cd /opt/klapp/klapp-ai-agent-rfq
git pull gitlab main
# Expected: includes 06c0831 (store_model_in_db)

# klapp-marketplace (Configuration tab + model management)
cd /opt/klapp/klapp-marketplace
git pull gitlab main
# Expected: includes 3687aaa (Configuration tab)

# klapp-email-processing-service (prior fixes: MinIO, attachments, LiteLLM Step B)
cd /opt/klapp/klapp-email-processing-service
git pull gitlab main

# klapp-rfq-sync-service (prior fixes: title fallback, customer_company)
cd /opt/klapp/klapp-rfq-sync-service
git pull gitlab main
```

### 4.2 Verify LiteLLM Database Exists
```bash
docker exec medusa_postgres psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'klapp_litellm'"
```
If missing:
```bash
cd /opt/klapp/klapp-ai-agent-rfq/docker/compose
docker compose -f docker-compose.prod.yml --profile init up db-init
```

### 4.3 Verify .env Has LiteLLM Keys
```bash
cd /opt/klapp/klapp-ai-agent-rfq/docker/compose
grep LITELLM .env
```
Expected: `LITELLM_MASTER_KEY=sk-<actual>`, `LITELLM_SALT_KEY=sk-<actual>`, `LITELLM_PORT=4000`
If missing:
```bash
echo "LITELLM_MASTER_KEY=sk-$(openssl rand -hex 32)" >> .env
echo "LITELLM_SALT_KEY=sk-$(openssl rand -hex 32)" >> .env
```

### 4.4 Rebuild & Restart Services
```bash
cd /opt/klapp/klapp-ai-agent-rfq/docker/compose

# Rebuild LiteLLM (picks up store_model_in_db: true)
docker compose -f docker-compose.prod.yml up -d litellm --build

# Rebuild marketplace backend (picks up Configuration tab)
cd /opt/klapp/klapp-marketplace
docker compose up -d marketplace-backend --build

# Rebuild email-processing-service (picks up LiteLLM Step B + prior fixes)
cd /opt/klapp/klapp-email-processing-service
docker compose up -d --build

# Rebuild rfq-sync-service (picks up title fallback + customer_company fixes)
cd /opt/klapp/klapp-rfq-sync-service
docker compose up -d --build
```

### 4.5 Verify Services Are Healthy
```bash
# LiteLLM
docker exec klapp-litellm curl -s http://localhost:4000/health/readiness
# Expected: {"status":"healthy"}

# Marketplace backend
curl -s localhost:9000/health

# Check logs for errors
docker logs klapp-litellm --tail 20
docker logs klapp-marketplace --tail 20
docker logs klapp-email-processor --tail 20
docker logs klapp-rfq-sync --tail 20
```

### 4.6 Test Configuration Tab on VPS
```bash
LITELLM_KEY=$(cd /opt/klapp/klapp-ai-agent-rfq/docker/compose && grep LITELLM_MASTER_KEY .env | cut -d= -f2)

# LiteLLM direct health
curl -s localhost:4000/health -H "Authorization: Bearer $LITELLM_KEY" | jq .

# Model configs via Marketplace
curl -s localhost:9000/admin/ai-agents/models/config \
  -H "Authorization: Bearer <admin-jwt>" | jq .
```

### 4.7 Test LiteLLM Model Routing (from Step B)
```bash
LITELLM_KEY=$(cd /opt/klapp/klapp-ai-agent-rfq/docker/compose && grep LITELLM_MASTER_KEY .env | cut -d= -f2)

curl -s http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -d '{"model":"gemini-2.0-flash","messages":[{"role":"user","content":"Reply with just: hello"}],"max_tokens":10}' | jq .
```

### 4.8 Post-Deploy Data Checks
```sql
-- Email DB (port 5432) — NULL titles from prior bug
SELECT count(*) FROM rfqs WHERE subject IS NULL OR subject = '';

-- MedusaJS DB (port 5434) — bad customer_company from prior bug
SELECT count(*) FROM rfq WHERE customer_company = 'customer';

-- Email DB (port 5432) — missing attachment URLs from prior bug
SELECT count(*) FROM rfq_attachments WHERE file_path IS NULL OR file_path = '';
```

### 4.9 End-to-End Email Pipeline Test
1. Send a test email to `rfq@klapp.ai`
2. Verify RFQ appears in email DB with title, customer info
3. Verify attachments have full MinIO URLs
4. Verify RFQ syncs to MedusaJS with all fields populated
5. Open `/app/ai-agents` → Configuration tab → verify models show health status

---

## Task 5: LiteLLM Step B — Switch to LiteLLM Provider (Optional)

Currently `LLM_PROVIDER=gemini` (direct calls). Switching to `litellm` routes all LLM calls through the proxy.

### 5.1 Switch Provider
```bash
cd /opt/klapp/klapp-ai-agent-rfq/docker/compose
sed -i 's/LLM_PROVIDER=gemini/LLM_PROVIDER=litellm/' .env
docker compose -f docker-compose.prod.yml up -d --force-recreate email-processor email-consumer
```

### 5.2 Verify
```bash
docker logs klapp-email-processor 2>&1 | grep -i litellm
# Expected: "LiteLLMClient initialized"
```

### 5.3 Rollback if Needed
```bash
sed -i 's/LLM_PROVIDER=litellm/LLM_PROVIDER=gemini/' .env
docker compose -f docker-compose.prod.yml up -d --force-recreate email-processor email-consumer
```

---

## Task 6: n8n Workflow Updates (Carried Over — Email Attachments)

**Context:** Email attachment delivery and inline CID image conversion were implemented locally but n8n workflows on VPS still use the old version. See `DAY-NEXT-DEPLOY.md` for full details.

### 6.1 Find Production Workflow IDs
```sql
-- Connect to n8n DB (port 5432, database klapp_workflows)
SELECT id, name FROM n8n.workflow_entity WHERE name LIKE '%email-sender%' OR name LIKE '%approved%';
SELECT id, name, type FROM n8n.credentials_entity WHERE type = 'httpHeaderAuth';
```

### 6.2 Update Workflow 30 (email-sender)
- Replace "Fetch Attachments" node `jsCode` with version from `klapp-ai-agent-rfq/services/n8n/workflows/30-email-sender.json`
- Change "Send Email" node `jsonBody` to `={{ $json._resendBodyJson }}`
- Update both `workflow_entity` AND `workflow_history` tables

### 6.3 Update Workflow 41 (approved-email-sender)
- Replace "Prepare Outbound Message" node `jsCode` with version from `klapp-ai-agent-rfq/services/n8n/workflows/41-approved-email-sender.json`
- Change "Publish" node message to `={{ $json.outbound_message_json }}`

### 6.4 Restart n8n
```bash
docker restart klapp-n8n compose-n8n-worker-1
```

---

## Task 7: Remaining Known Issues

- [ ] **Deactivate old Safety Net workflow** — Duplicate `3pL0DLWPD7mpPXZl` still active in n8n, should be deactivated (active one is `bItO_nP7yPFz8iYMdxH4_`)
- [ ] **6 attachments with no file in MinIO** — Need IMAP re-import or manual PDF upload
- [ ] **n8n sync for new email** — After VPS deployment, go to Platform Settings and click "Sync to n8n" to push `commercial@ecorporates.com` credentials to n8n IMAP trigger
- [ ] **LiteLLM Step C** — enrichment-service, pricing-service, n8n workflows (05, 10, 12) still call LLM providers directly, not through LiteLLM (future work)

---

## Quick Reference

| Item | Value |
|------|-------|
| VPS | `root@82.29.178.249` (alias `klapp-vps`) |
| klapp-ai-agent-rfq VPS path | `/opt/klapp/klapp-ai-agent-rfq` |
| klapp-marketplace VPS path | `/opt/klapp/klapp-marketplace` |
| LiteLLM internal URL | `http://litellm:4000` |
| LiteLLM external URL | `https://llm.klapp.ai` |
| LiteLLM Admin UI | `http://localhost:4000/ui` on VPS |
| Marketplace Admin | `https://admin.klapp.ai/app/ai-agents` |
| Git remote | `gitlab` for all repos |
| Docker network | `klappnetwork` |
| Email DB | `klapp_ai_procurement` on port 5432 |
| MedusaJS DB | `klapp-backend` on port 5434 |
| n8n DB | `klapp_workflows`, schema `n8n`, port 5432 |
