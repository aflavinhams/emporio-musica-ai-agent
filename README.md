# Empório da Música — AI Customer Support Agent

A conversational AI assistant for **Empório da Música**, a fictional Brazilian musical instrument retailer. Built in Python, the project combines a locally hosted large language model (LLM), function calling, retrieval-augmented generation (RAG), and deterministic business rules to answer customer questions using the supplied catalog, order records, promotions, and store policy document.

The assistant interacts with customers in **Brazilian Portuguese** through a command-line interface.

## Features

- **Product discovery:** search musical instruments by name, category, availability, and maximum price. Search normalization handles common Portuguese variations such as *guitarra elétrica*, *guitarras elétricas*, and *violões*.
- **Product comparison:** compare two catalog items using recorded prices and specifications rather than invented attributes.
- **Promotions:** retrieve active offers, promotional prices, stock, and discount information.
- **Order inquiries:** retrieve a matching order's status and items after collecting its order ID and registered email.
- **Store policies:** retrieve relevant passages from the supplied PDF to answer questions about returns, refunds, payments, shipping, and other documented policies.
- **Multi-turn conversations:** preserve relevant messages and tool results across follow-up questions.
- **Conversation examples:** save actual interactions as Markdown transcripts for review.

## Architecture

```text
Customer (CLI)
    |
    v
main.py
    |
    v
MusicStoreAgent (src/agent/agent.py)
    |-- Intent-specific safeguards and response validation
    |-- Local LLM through Ollama's OpenAI-compatible API
    |-- Function calling
    |     |-- Catalog search
    |     |-- Active and product promotions
    |     |-- Order status and order items
    |     |-- Product comparison
    |     `-- Policy retrieval
    |
    `-- Conversation history
              |
              v
       Customer-facing answer (pt-BR)
```

**Language model:** Qwen3 4B (`qwen3:4b`) hosted locally with Ollama. The Python `openai` client connects to Ollama through its OpenAI-compatible endpoint. The solution does not require a paid hosted LLM API for its default configuration.

**RAG:** Store policy passages are extracted from `data/politicas_da_loja.pdf` with `pypdf`, indexed using TF-IDF from scikit-learn, and retrieved by textual similarity. Results include source page information. Return-related queries use policy-focused retrieval terms to avoid retrieving shipping information instead of the relevant return policy.

**Deterministic safeguards:** Python code enforces selected boundaries independently of model output. In particular, catalog results are formatted from verified records, explicit comparisons use stored specifications, questions involving purchase versus receipt dates are treated separately, and requests to execute unsupported returns or refunds are blocked.

## Project structure

```text
.
├── main.py
├── requirements.txt
├── .env.example
├── data/
│   ├── products.csv
│   ├── categories.csv
│   ├── customers.csv
│   ├── orders.csv
│   ├── order_items.csv
│   ├── promotions.csv
│   └── politicas_da_loja.pdf
├── src/
│   ├── agent/
│   │   ├── agent.py
│   │   └── prompts.py
│   ├── tools/
│   │   ├── catalog.py
│   │   ├── comparison.py
│   │   ├── promotions.py
│   │   └── orders.py
│   └── retrieval/
│       └── policy_retriever.py
├── tests/
│   ├── test_agent.py
│   ├── test_catalog.py
│   ├── test_catalog_search_variants.py
│   ├── test_comparison.py
│   ├── test_orders.py
│   ├── test_policy_retriever.py
│   ├── test_policy_routing.py
│   ├── test_promotions.py
│   └── test_return_policy.py
└── examples/
    ├── 01_product_recommendation.md
    ├── 02_active_promotions.md
    ├── 03_return_policy.md
    ├── 04_order_tracking.md
    └── 05_out_of_scope.md
```

The `data/` directory contains the challenge's reference datasets; it is not a live connection to an e-commerce platform. Make sure these files are available locally when running the application.

## Prerequisites

- Python 3.10 or later
- [Ollama](https://ollama.com/) installed and running
- The `qwen3:4b` model downloaded locally
- The required CSV and PDF input files in `data/`

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/aflavinhams/emporio-musica-ai-agent.git
cd emporio-musica-ai-agent
```

### 2. Create a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start Ollama and download the model

```bash
ollama pull qwen3:4b
```

Ensure the Ollama server is running, for example with `ollama serve` if it is not already running as a service.

### 5. Configure the environment

Copy `.env.example` to `.env` and ensure the following settings are present:

```dotenv
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen3:4b
```

The default local configuration uses Ollama and does not require an OpenAI API key. Keep `.env` outside version control.

### 6. Run the assistant

```bash
python main.py
```

Type customer messages in Portuguese. Enter `sair` to close the session.

## Example interactions

**Product recommendation**

> Customer: Estou começando a aprender violão e tenho até R$ 800. Quais opções vocês recomendam?
>
> Assistant: Searches the supplied catalog, applies the requested budget, and presents available instruments with recorded prices and stock.

**Discount policy**

> Customer: Se eu pagar no PIX, consigo mais 5% de desconto?
>
> Assistant: Retrieves the payment policy and explains that the 5% PIX discount cannot be combined with promotional prices.

**Return eligibility**

> Customer: Comprei um violão há 5 dias. Posso devolver?
>
> Assistant: Explains that the 7-day online withdrawal period is counted from **receipt**, not purchase, and asks when the instrument was received before assessing the reported timeframe.

**Order status**

> Customer: Em que dia exatamente meu pedido foi entregue?
>
> Assistant: Does not invent an actual delivery date when the order record includes only an estimated date.

Full example transcripts are available in [`examples/`](examples/), covering product recommendations, promotions, return policies, order tracking, and requests outside the store's catalog.

To save an interaction from the CLI:

```text
/save 03_return_policy
```

The example transcripts are demonstrations of the local application, not evidence of a production deployment.

## Tools and data access

| Tool | Responsibility | Data source |
| --- | --- | --- |
| `search_products` | Product search, price and stock filters | Products and categories CSVs |
| `compare_products` | Verified product comparisons | Product catalog |
| `get_active_promotions` | Currently marked active promotions in the dataset | Promotions CSV |
| `get_product_promotion` | Promotion information for a product | Promotions CSV |
| `get_order_status` | Order status lookup | Orders and customer records |
| `get_order_items` | Items associated with an order | Order items and related records |
| `search_policies` | Relevant policy passages with page references | Store policy PDF |

Only predefined local functions are exposed through the agent's tool allowlist. Tool arguments are filtered against each Python function's signature before execution.

## Reliability and safety decisions

1. **Source-grounded responses.** Product prices, stock, and specifications come from CSV records; policy answers are supported by PDF retrieval.
2. **Deterministic catalog formatting.** When a single catalog search returns product records, the application formats the verified results directly, limiting model-generated product hallucinations.
3. **Purchase date is not receipt date.** For specified return questions, the agent checks whether a receipt date is missing before discussing the 7-day withdrawal window.
4. **Unsupported operations are blocked.** The assistant can explain returns and refunds but cannot initiate them, approve them, issue refunds, charge payments, or complete checkout.
5. **Response validation.** Placeholder text, raw tool-call JSON, and certain unsupported action claims trigger a retry or a safe fallback.
6. **Order data handling.** Order lookups require the order identifier and registered email; order tool inputs and outputs are redacted in the terminal's tool logs.

These safeguards target observed failure modes; they are not a guarantee that every model response will be factually correct.

## Tests

Run the complete unit test suite from the repository root:

```bash
python -m unittest discover -s tests -v
```

**Latest verified local result:** 63 tests passed (reported during development). Coverage includes catalog filtering and search variants, promotions, order lookups, policy retrieval/routing, product comparison, return safeguards, and agent tool orchestration. This count is a development snapshot, not an automatically updated CI badge.

To run only the catalog-related tests:

```bash
python -m unittest discover -s tests -p "test_catalog*.py" -v
```

Tests mock model/tool interactions where appropriate; they do not replace end-to-end checks with the running Ollama model.

## AI-assisted development

**Tool used:** ChatGPT (OpenAI), as a coding and development assistant.

ChatGPT supported implementation planning, Python code drafting and review, debugging, automated test design, and technical documentation. The development workflow was iterative: suggested changes were applied to the local project, exercised with the Ollama-powered agent, checked against the provided CSV datasets and store policy PDF, and adjusted when actual results revealed issues.

Examples of issues identified and resolved during this process include Portuguese catalog query normalization (such as *guitarras elétricas*), improving retrieval of the online return policy, distinguishing purchase dates from receipt dates, preventing the assistant from claiming it can process returns or refunds, and adding regression tests for those behaviors.

AI-generated suggestions were not treated as verified by default. The final implementation decisions were guided by the challenge requirements, the available data, local test results, and observed customer conversations. Known limitations and remaining production-readiness gaps are documented below.

## Limitations and potential improvements

- **Not a production commerce service:** no live inventory sync, purchase processing, payment execution, return initiation, or refund processing.
- **Simplified order verification:** matching an order ID with a registered email is not strong authentication and should not be used as a production authorization mechanism.
- **Static reference data:** product availability, order states, and promotions reflect the supplied datasets, not real-time store systems.
- **Local model limitations:** a small LLM may misunderstand user intent or produce unsupported language despite validation; deterministic handling currently targets selected high-risk scenarios.
- **Keyword-based intent handling:** several safety and policy-routing rules depend on Portuguese expressions and may miss paraphrases.
- **Lexical RAG:** TF-IDF retrieval is lightweight and transparent but may miss semantically relevant passages. Hybrid or embedding-based retrieval with source validation could improve recall.
- **Interface and operations:** a CLI is provided for demonstration; the project does not include a hosted API, web interface, authentication service, or deployment pipeline.

## Technology stack

Python · Ollama · Qwen3 4B · OpenAI-compatible API · Function Calling · pypdf · scikit-learn (TF-IDF) · CSV · `unittest`

## Context

Developed as a technical exercise for an AI engineering application. Empório da Música is a fictional retailer, and the project uses its provided reference datasets and policy document solely for the exercise.
