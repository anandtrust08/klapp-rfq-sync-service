# AI/LLM Configuration Guide - Klapp Platform

> **Last Updated:** 2026-02-21
> **Audience:** Developers, DevOps, Architects

---

## Table of Contents

1. [Overview](#1-overview)
2. [Service-by-Service AI Inventory](#2-service-by-service-ai-inventory)
3. [API Key Locations & Management](#3-api-key-locations--management)
4. [Hardcoded Values Audit](#4-hardcoded-values-audit)
5. [Architecture Assessment & Best Practices](#5-architecture-assessment--best-practices)
6. [Security Issues & Recommendations](#6-security-issues--recommendations)
7. [Guide: Adding a New LLM Provider (e.g., OpenAI/ChatGPT)](#7-guide-adding-a-new-llm-provider)

---

## 1. Overview

The Klapp platform uses a **multi-provider LLM strategy** across 6 services:

| Provider | Role | API Key Env Var |
|----------|------|-----------------|
| **Google Gemini** | Primary production LLM | `GOOGLE_API_KEY` |
| **Anthropic Claude** | Fallback / enrichment | `ANTHROPIC_API_KEY` |
| **Ollama (local)** | Local dev / offline | None (runs locally) |
| **OpenAI** | Configured but NOT active | `OPENAI_API_KEY` (placeholder) |
| **sentence-transformers** | Embeddings (local) | None (runs locally) |

**Provider Priority Chain:** Gemini -> Claude -> Ollama

---

## 2. Service-by-Service AI Inventory

### 2.1 klapp-email-processing-service (Python)

**Role:** Heaviest AI consumer - RFQ extraction, email classification, document processing

| Aspect | Detail |
|--------|--------|
| **Providers** | Gemini (primary), Claude (fallback), Ollama (dev) |
| **Gateway** | `src/services/llm/gateway.py` - Singleton with cross-provider fallback |
| **Config** | `src/config.py` |
| **Prompt Mgmt** | `src/services/prompt/prompt_service.py` - DB-driven with Redis cache |
| **Embeddings** | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dims) |
| **Models** | `gemini-2.0-flash`, `claude-sonnet-4-20250514`, `llama3.1:8b` |

**Env vars consumed:**
```
LLM_PROVIDER=gemini
GOOGLE_API_KEY=<key>
GEMINI_MODEL=gemini-2.0-flash
GEMINI_FALLBACK_MODEL=gemini-2.0-flash
GEMINI_MAX_TOKENS=8192
GEMINI_TIMEOUT=120
ANTHROPIC_API_KEY=<key>
CLAUDE_MODEL=claude-sonnet-4-20250514
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_TIMEOUT=120
LLAMA_PARSE_API_KEY=<optional, for PDF parsing>
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSION=384
EMBEDDING_BATCH_SIZE=32
```

**Key files:**
- `src/services/llm/gateway.py` - LLMGateway (OllamaClient, AnthropicClient, GeminiClient)
- `src/services/classification/ai_classifier.py` - Email classification
- `src/agents/product_classifier/` - Product categorization
- `src/agents/email_parser/prompt_driven_email_parser.py` - RFQ extraction
- `src/agents/document_processor/` - Attachment processing

---

### 2.2 klapp-supplier-discovery (TypeScript monorepo)

#### 2.2a Enrichment Service (`services/klapp-enrichment-service/`)

| Aspect | Detail |
|--------|--------|
| **Provider** | Anthropic Claude only |
| **SDK** | `@anthropic-ai/sdk` |
| **Config** | `src/config/index.ts` |
| **Code** | `src/services/claude.service.ts` |
| **Model** | `claude-3-sonnet-20240229` |
| **Use Case** | Supplier data enrichment, JSON extraction |

**Env vars consumed:**
```
ANTHROPIC_API_KEY=<key>
CLAUDE_MODEL=claude-3-sonnet-20240229
MAX_TOKENS_PER_REQUEST=4000
COST_PER_1K_INPUT_TOKENS=0.003
COST_PER_1K_OUTPUT_TOKENS=0.015
```

#### 2.2b Shared TS Package (`packages/shared-ts/src/gemini/`)

| Aspect | Detail |
|--------|--------|
| **Provider** | Google Gemini |
| **Config** | `src/gemini/config.ts` |
| **Code** | `src/gemini/client.ts` - Production client with Redis rate limiting |
| **Rate Limiter** | `src/gemini/rate-limiter.ts` - Redis-based token bucket |
| **Model** | `gemini-2.0-flash-exp` |

**Env vars consumed:**
```
GEMINI_API_KEY=<key>
GEMINI_MODEL=gemini-2.0-flash-exp
GEMINI_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta
GEMINI_RATE_LIMIT_RPM=10
GEMINI_RATE_LIMIT_BURST=3
GEMINI_RETRY_MAX_ATTEMPTS=3
GEMINI_REQUEST_TIMEOUT_MS=30000
```

---

### 2.3 klapp-marketplace (MedusaJS backend, TypeScript)

| Aspect | Detail |
|--------|--------|
| **Providers** | OpenAI, Claude, Gemini, Local (all supported) |
| **Config** | `backend/src/modules/ai-agent/llm-service.ts` |
| **Use Case** | Communications summarization |
| **Endpoint** | `/api/admin/communications/summarize/` |

**Env vars consumed:**
```
GOOGLE_API_KEY=<key>
GEMINI_MODEL=gemini-2.0-flash
AI_ANALYSIS_ENABLED=true
OPENAI_API_KEY=<optional>
ANTHROPIC_API_KEY=<optional>
```

---

### 2.4 klapp-ai-agent-rfq

#### 2.4a Legacy Python agents (`applications/klapp-ai/ai-agents/`)

| Aspect | Detail |
|--------|--------|
| **Provider** | Ollama only |
| **Config** | `core/config.py` |
| **Code** | `services/llm_service.py`, `email_parser.py` |

#### 2.4b n8n Workflows (`services/n8n/workflows/`)

| Aspect | Detail |
|--------|--------|
| **Provider** | Gemini (via n8n LLM node) |
| **API Key** | `N8N_GOOGLE_API_KEY` (mapped from `GOOGLE_API_KEY`) |
| **Workflow** | `10-classification-bridge.json` |

#### 2.4c Docker Compose (orchestrator for all services)

The file `docker/compose/.env` is the **primary orchestration .env** that feeds API keys into Docker containers. It maps keys to services via `docker-compose.yml`:

```yaml
# Example from docker-compose.yml
email-processor:
  environment:
    - GOOGLE_API_KEY=${GOOGLE_API_KEY}
    - GEMINI_MODEL=${GEMINI_MODEL}
n8n:
  environment:
    - N8N_GOOGLE_API_KEY=${GOOGLE_API_KEY}
```

---

### 2.5 supplier-discovery-service (Legacy Python)

| Aspect | Detail |
|--------|--------|
| **Providers** | Ollama (default), Claude, OpenAI |
| **Config** | `app/config.py` |
| **Factory** | `app/llm/factory.py` - Auto-detects provider from credentials |
| **Providers** | `app/llm/providers/` - ollama.py, anthropic.py, openai.py |
| **Prompt Mgmt** | `app/services/prompt_manager.py` - DB-driven with cache |

**Env vars consumed:**
```
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=2048
LLM_TIMEOUT=30.0
OLLAMA_BASE_URL=http://localhost:11434
ANTHROPIC_API_KEY=<optional>
ANTHROPIC_MODEL=claude-3-haiku-20240307
OPENAI_API_KEY=<optional>
OPENAI_MODEL=gpt-4o-mini
```

---

### 2.6 quote-processing-service (Python)

| Aspect | Detail |
|--------|--------|
| **Provider** | Ollama only (local, no API key) |
| **Config** | `app/utils/config.py` |
| **Client** | `app/utils/ollama_client.py` |
| **Agents** | `app/agents/` - quote_analyzer, proposal_generator, pricing_intelligence |

---

### 2.7 Services WITHOUT AI

- `klapp-rfq-sync-service` - Pure data sync (Kafka -> MedusaJS)
- `rfq-email-notifier` - Kafka consumer for notifications
- `klapp-ai-frontend` - Frontend UI only

---

## 3. API Key Management

### 3.1 Single Source of Truth

**YES - there is ONE central .env file** for all AI/LLM API keys:

```
klapp-ai-agent-rfq/docker/compose/.env
```

This file contains:
- `GOOGLE_API_KEY` - Google Gemini (primary LLM)
- `ANTHROPIC_API_KEY` - Anthropic Claude (fallback / enrichment)
- `OPENAI_API_KEY` - OpenAI (reserved, currently empty)

### 3.2 How Keys Flow to Services

**Docker (primary):** `docker-compose.yml` reads the central `.env` and injects keys into each container:

```
central .env (GOOGLE_API_KEY, ANTHROPIC_API_KEY)
    ├── docker-compose.yml → email-processor (GOOGLE_API_KEY, ANTHROPIC_API_KEY)
    ├── docker-compose.yml → email-consumer (same)
    ├── docker-compose.yml → email-classifier (same)
    ├── docker-compose.yml → ai-agent (GOOGLE_API_KEY, ANTHROPIC_API_KEY)
    ├── docker-compose.yml → n8n (N8N_GOOGLE_API_KEY)
    ├── docker-compose.yml → n8n-worker (N8N_GOOGLE_API_KEY)
    ├── docker-compose.yml → klapp-enrichment-service (ANTHROPIC_API_KEY)
    └── docker-compose.yml → klapp-pricing-service (GEMINI_API_KEY, ANTHROPIC_API_KEY)
```

**Local dev (outside Docker):** Run `./scripts/setup-dev-env.sh` to distribute keys from the central `.env` to per-service `.env` files.

### 3.3 Key Rotation Procedure

To rotate an API key:
1. Update the key in `klapp-ai-agent-rfq/docker/compose/.env`
2. Restart Docker services: `docker compose restart`
3. If running services locally, re-run `./scripts/setup-dev-env.sh`
4. For production, update the `.env` on the VPS and restart

### 3.4 Adding a New API Key

Checklist:
1. Add the key to `klapp-ai-agent-rfq/docker/compose/.env`
2. Add placeholder to `.env.example` and `.env.prod.example`
3. Map `${NEW_KEY}` in `docker-compose.yml` for each service that needs it
4. Map in `docker-compose.prod.yml` for production
5. Update `scripts/setup-dev-env.sh` to distribute the new key
6. Update this documentation

### 3.5 Per-Service .env Files (Model Config Only)

Per-service `.env` files should contain **model names, timeouts, and service-specific config** but NOT API keys:

```
klapp-email-processing-service/.env  → LLM_PROVIDER, GEMINI_MODEL, etc.
klapp-marketplace/backend/.env       → GEMINI_MODEL, AI_ANALYSIS_ENABLED, etc.
```

### 3.6 Security Measures

- **Pre-commit hooks**: `detect-secrets` prevents accidentally committing API keys
- **`.gitignore`**: All `.env` files are excluded from git
- **Central management**: Single file to audit, rotate, and secure

---

## 4. Hardcoded Values Audit

### 4.1 Hardcoded Model Names (ALL acceptable - used as defaults)

All model names in code are used as **fallback defaults** with `os.getenv("VAR", "default")` pattern:

| File | Hardcoded Value | Pattern | Verdict |
|------|----------------|---------|---------|
| `email-processing/src/config.py:122` | `llama3.1:8b` | `os.getenv("OLLAMA_MODEL", "llama3.1:8b")` | OK |
| `email-processing/src/config.py:126` | `gemini-2.0-flash` | `os.getenv("GEMINI_MODEL", "gemini-2.0-flash")` | OK |
| `email-processing/src/config.py:133` | `claude-sonnet-4-20250514` | `os.getenv("CLAUDE_MODEL", ...)` | OK |
| `email-processing/src/services/llm/gateway.py:179` | `gemini-2.0-flash` | Fallback default | OK |
| `supplier-discovery/app/config.py:89` | `llama3.1:8b` | `os.getenv()` default | OK |
| `supplier-discovery/app/config.py:99` | `claude-3-haiku-20240307` | `os.getenv()` default | OK |
| `supplier-discovery/app/config.py:103` | `gpt-4o-mini` | `os.getenv()` default | OK |
| `shared-ts/src/gemini/config.ts:10` | `gemini-2.0-flash-exp` | Config default | OK |

### 4.2 Hardcoded API Endpoints

| File | URL | Verdict |
|------|-----|---------|
| `gateway.py:124` | `https://api.anthropic.com/v1/messages` | OK - Standard endpoint |
| `gateway.py:206` | `https://generativelanguage.googleapis.com/v1beta/models/...` | OK - Standard endpoint |
| Various | `http://localhost:11434` | OK - Local Ollama default |

### 4.3 Hardcoded Temperature/Tokens/Timeouts

All use sensible defaults - `temperature=0.1` for extraction tasks, `max_tokens=8192` for Gemini, `timeout=120s`. These are acceptable as defaults.

### 4.4 CRITICAL: Hardcoded API Key Found

**File:** `klapp-email-processing-service/test_claude_vs_ollama.py` (line 22)
**Issue:** A real Anthropic API key is hardcoded in a test file
**Action Required:** Revoke this key immediately on the Anthropic console and regenerate

---

## 5. Architecture Assessment & Best Practices

### 5.1 Compliance Matrix

| Category | email-processing | supplier-discovery (py) | klapp-marketplace | klapp-supplier-discovery (ts) | quote-processing |
|----------|:-:|:-:|:-:|:-:|:-:|
| Provider Abstraction | **Gateway** | **Factory** | Switch stmt | Single-provider | Single-provider |
| Error Handling | Multi-level fallback | Retry + backoff | Basic catch | Retry + backoff | No retry |
| Rate Limiting | None | None | None | **Redis token bucket** | None |
| Cost Tracking | Token counts only | Token counts only | **Cost calculation** | **Cost calculation** | None |
| Retry Logic | Model-level fallback | Exponential backoff | Timeout only | Exponential + jitter | None |
| Prompt Management | **DB + Redis cache** | **DB + cache** | Hardcoded | Hardcoded | Hardcoded |

### 5.2 What's Done Well

1. **email-processing-service**: Best implementation overall
   - LLMGateway singleton with cross-provider fallback (Gemini -> Claude -> Ollama)
   - DB-driven prompt management with Redis caching and versioning
   - Config-driven model selection with env var overrides

2. **supplier-discovery-service (Python)**: Clean factory pattern
   - Abstract `LLMProvider` base class with separate provider implementations
   - Factory function for provider instantiation
   - Configurable retry with exponential backoff

3. **klapp-supplier-discovery (Gemini client)**: Production-grade rate limiting
   - Redis-based distributed token bucket algorithm
   - Exponential backoff with jitter to prevent thundering herd
   - Batch processing with rate-limit awareness

### 5.3 What Needs Improvement

| Issue | Impact | Services Affected |
|-------|--------|-------------------|
| **No centralized API key management** | Key rotation requires editing 3+ files | All |
| **No rate limiting on most services** | Risk of hitting provider rate limits / cost overrun | email-processing, marketplace, supplier-discovery |
| **No persistent cost logging** | Cannot track spend over time | All (cost is calculated but not stored) |
| **Inconsistent provider abstraction** | TypeScript services lack proper abstraction | marketplace, klapp-supplier-discovery, enrichment |
| **No unified observability** | Token usage scattered across services | All |
| **Hardcoded prompts in TypeScript** | Cannot update prompts without code deploy | marketplace, klapp-supplier-discovery |
| **No secret scanning in CI/CD** | API keys can leak into git | All |

### 5.4 Industry Best Practices Comparison

| Best Practice | Current State | Recommendation |
|---------------|---------------|----------------|
| **Secrets management** (Vault, AWS SSM, etc.) | .env files per service | Use HashiCorp Vault, AWS SSM, or at minimum a single `.env` source |
| **Provider abstraction layer** | Python: good, TS: poor | Create shared TS package with provider interface |
| **Centralized config** | Fragmented | Use config service or shared secrets store |
| **Rate limiting** | Only Gemini in one service | Add rate limiting to all external API calls |
| **Cost monitoring dashboard** | Not implemented | Log token usage to DB, build Grafana dashboard |
| **Prompt versioning & A/B testing** | Partially (email-processing only) | Extend DB-driven prompts to all services |
| **Circuit breaker pattern** | Not implemented | Add circuit breakers for provider failover |
| **API key rotation** | Manual, multi-file | Automate rotation with secrets manager |
| **Pre-commit secret scanning** | Not implemented | Add `gitleaks` or `detect-secrets` pre-commit hook |

---

## 6. Security Issues & Recommendations

### 6.1 Issues Fixed (2026-02-21)

- [x] **Removed hardcoded Anthropic API key** from `klapp-email-processing-service/test_claude_vs_ollama.py` - now reads from `os.getenv("ANTHROPIC_API_KEY", "")`
- [x] **Fixed mislabeled key** in `klapp-supplier-discovery/.env` - removed incorrect `ANTHROPIC_API_KEY` that contained a Google API key value
- [x] **Consolidated API keys** into single source: `klapp-ai-agent-rfq/docker/compose/.env`
- [x] **Removed duplicate API keys** from `klapp-email-processing-service/.env` and `klapp-marketplace/backend/.env`
- [x] **Added pre-commit hooks** (`detect-secrets`) to 4 repos

### 6.2 Manual Action Required

- **Revoke the leaked Anthropic API key** on https://console.anthropic.com and generate a new one
- **Run `detect-secrets scan > .secrets.baseline`** in each repo to initialize the baseline
- **Install pre-commit**: `pip install pre-commit && pre-commit install` in each repo

### 6.3 Long-term Architecture

- Adopt a secrets manager (HashiCorp Vault, Infisical, or cloud-native like AWS SSM)
- Implement API key rotation automation
- Add cost alerts per provider

---

## 7. Guide: Adding a New LLM Provider

### Step-by-step: Adding OpenAI/ChatGPT (or any new LLM)

#### Step 1: Add env vars to Docker Compose .env

**File:** `klapp-ai-agent-rfq/docker/compose/.env`
```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-actual-key
OPENAI_MODEL=gpt-4o
OPENAI_MAX_TOKENS=4096
OPENAI_TEMPERATURE=0.1
OPENAI_TIMEOUT=120
```

Also update `.env.example` and `.env.prod.example` with placeholder values.

#### Step 2: Update docker-compose.yml

**File:** `klapp-ai-agent-rfq/docker/compose/docker-compose.yml`

Add the env vars to each service that needs OpenAI:
```yaml
email-processor:
  environment:
    - OPENAI_API_KEY=${OPENAI_API_KEY:-}
    - OPENAI_MODEL=${OPENAI_MODEL:-gpt-4o}
    - OPENAI_MAX_TOKENS=${OPENAI_MAX_TOKENS:-4096}
```

#### Step 3: Service-specific implementation

Each service has a different pattern. Here's what to do for each:

##### klapp-email-processing-service (Python - Gateway pattern)

**A. Update config** (`src/config.py`):
```python
# Add OpenAI config section
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "4096"))
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "120"))
```

**B. Add OpenAI client** to `src/services/llm/gateway.py`:
```python
class OpenAIClient:
    def __init__(self, api_key: str, model: str, max_tokens: int, timeout: int):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout

    async def complete(self, prompt: str, system_prompt: str = "", **kwargs) -> dict:
        import openai
        client = openai.AsyncOpenAI(api_key=self.api_key)
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=self.max_tokens,
            temperature=kwargs.get("temperature", 0.1),
        )
        return {
            "success": True,
            "content": response.choices[0].message.content,
            "tokens": {
                "prompt": response.usage.prompt_tokens,
                "completion": response.usage.completion_tokens,
            }
        }
```

**C. Register in gateway fallback order:**
```python
class LLMGateway:
    FALLBACK_ORDER = ["gemini", "openai", "anthropic", "ollama"]
    # Update _initialize_clients() to include OpenAI
```

**D. Add dependency:**
```bash
pip install openai
# Add to requirements.txt: openai>=1.0.0
```

##### supplier-discovery-service (Python - Factory pattern)

Already has OpenAI provider at `app/llm/providers/openai.py`. Just set the env vars:
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4o
```

##### klapp-marketplace (TypeScript - direct implementation)

Already has `callOpenAI()` in `llm-service.ts`. Just set:
```bash
OPENAI_API_KEY=sk-your-key
```

##### klapp-supplier-discovery (TypeScript - needs new provider)

Create a new OpenAI client mirroring the Gemini client pattern:
```
packages/shared-ts/src/openai/
├── client.ts          # OpenAIClient class
├── config.ts          # Configuration & defaults
├── rate-limiter.ts    # Reuse existing Redis rate limiter
└── index.ts           # Exports
```

##### quote-processing-service (Python - Ollama only)

Requires significant refactoring to add multi-provider support. Consider:
1. Extract `OllamaClient` into a base `LLMClient` interface
2. Add OpenAI implementation
3. Add factory/selection logic

#### Step 4: Update n8n workflows (if needed)

For n8n classification workflows, add OpenAI credentials:
1. Login to n8n UI
2. Add new credential: OpenAI API Key
3. Update workflow `10-classification-bridge.json` to use OpenAI node instead of Gemini

#### Step 5: Testing checklist

- [ ] Verify API key is loaded from env (not hardcoded)
- [ ] Test with rate limiting enabled
- [ ] Test fallback: disable OpenAI key and verify fallback to next provider
- [ ] Compare output quality against current Gemini baseline
- [ ] Monitor token usage and costs for first 24 hours
- [ ] Update cost calculation with OpenAI pricing

#### Step 6: Update the central .env

Add the new API key to the **single source of truth** only:
```
klapp-ai-agent-rfq/docker/compose/.env          <-- actual key value
klapp-ai-agent-rfq/docker/compose/.env.example   <-- placeholder
klapp-ai-agent-rfq/docker/compose/.env.prod.example <-- placeholder
```

Then map it in `docker-compose.yml` and `docker-compose.prod.yml` for services that need it.
Update `scripts/setup-dev-env.sh` to distribute the new key for local dev.

---

## Appendix: Quick Reference

### All AI-Related Env Vars (master list)

```bash
# Provider Selection
LLM_PROVIDER=gemini|claude|ollama|openai

# Google Gemini
GOOGLE_API_KEY=
GEMINI_API_KEY=                    # Used by klapp-supplier-discovery
GEMINI_MODEL=gemini-2.0-flash
GEMINI_FALLBACK_MODEL=gemini-1.5-flash
GEMINI_MAX_TOKENS=8192
GEMINI_TIMEOUT=120
GEMINI_RATE_LIMIT_RPM=10
GEMINI_RATE_LIMIT_BURST=3

# Anthropic Claude
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-sonnet-4-20250514
MAX_TOKENS_PER_REQUEST=4000

# OpenAI (currently placeholder in most services)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Ollama (Local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_TIMEOUT=120
OLLAMA_TEMPERATURE=0.1

# Embeddings (Local - no API key)
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
EMBEDDING_BATCH_SIZE=32
ENABLE_EMBEDDINGS=true
SIMILARITY_THRESHOLD=0.5
MAX_SIMILAR_PRODUCTS=5

# Optional
LLAMA_PARSE_API_KEY=               # PDF parsing
AI_CONFIDENCE_THRESHOLD=0.75
AI_ANALYSIS_ENABLED=true

# n8n (mapped from GOOGLE_API_KEY)
N8N_GOOGLE_API_KEY=
```
