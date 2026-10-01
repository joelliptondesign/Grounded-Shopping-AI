# How it works

The shopping app connects a conversational interface to a Python recommendation engine and language models. One server runs the backend and serves the interface.

## From a message to a response

1. **Understand the request.** The model identifies what the shopper wants to do and extracts changes to their preferences.
2. **Update the conversation.** The application keeps existing preferences, applies changes, and resolves references against recently displayed products.
3. **Handle the shopping task.** Recommendation requests check requirements and score eligible options. Comparisons and factual questions use the relevant product or review information.
4. **Choose and check the result.** For recommendations, the model selects useful options from the eligible set. Application rules check the selection and supporting reasons.
5. **Present the answer.** The application builds cards, a table, product details, or a conversational response. Generated language is checked before delivery, with a retry and fallback if needed.

Validated cards and comparisons can appear while the accompanying explanation is still being prepared. The interface keeps a loading cue visible until the turn is complete.

## What the application remembers

Each session holds the shopper's requirements, preferences, recent conversation, and recently displayed products. A budget change updates the budget without resetting the rest. Displayed product identities and order help resolve phrases such as “the first two.” Sessions are stored in server memory, so restarting the server resets them.

## How recommendations work

The engine separates requirements from preferences. An absolute spending limit excludes products; an approximate budget allows nearby alternatives with explained tradeoffs. Eligible products receive scores based on represented attributes and shopper priorities. The model uses those signals to choose a useful shortlist, and application rules validate its choices.

Catalog and review records provide the evidence. Frontend details such as product photos and delivery labels are presentation fixtures; they do not influence recommendation decisions.

## Run locally

Use Python 3.9 or later. From the repository folder, create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

On Windows, activate with `.venv\Scripts\activate` instead.

For Live mode, copy `.env.example` to `.env` and enter your own `OPENAI_API_KEY`. Keep this file private. Optional model settings are listed in the example.

Start the app:

```bash
python -m uvicorn api.server:app --reload --port 8000
```

Open [localhost:8000](http://localhost:8000), then use the three-dot menu to choose **Demo** or **Live**. Demo uses scripted responses; Live uses the backend and requires an API key. Switching modes starts a fresh conversation. Press **Control+C** in the terminal to stop the server.

## Run checks

Unit tests use mocked model calls:

```bash
python -m unittest discover
```

The repeatable behavior evaluation also runs without model calls:

```bash
python evals/runner.py --deterministic-only
```

For live evaluations, scenario selection, and reading results, see the [evaluation guide](EVALUATION.md). Live runs make API calls and incur usage charges.

## Where to look next

| Area | Files and guide |
| --- | --- |
| Interface and interaction behavior | [Frontend guide](../frontend/README.md) |
| Connection between interface and engine | [API guide](../api/README.md) |
| Conversation and preferences | [Conversation](../engine/conversation.py), [preference updates](../engine/preference_extraction.py) |
| Recommendations | [Filtering and scoring](../engine/decision.py), [model selection of products](../engine/shopping_selection.py) |
| Response checks and presentation | [Grounding](../engine/grounding.py), [presentation](../engine/presentation.py) |
| Detailed product architecture | [Architecture guide](ARCHITECTURE.md) |
| Model quality, speed, and cost | [Model comparison](MODEL_BAKEOFF.md) |
| Hosting | [Deployment guide](DEPLOYMENT.md) |

The repository also retains a legacy Streamlit debug interface. After installing the development dependencies above, start it with `streamlit run streamlit_app.py`.

## Groundwork local checks

The application remains Python-based. Repository documentation review additionally requires Git and Node.js 22 or newer, with no Node packages to install. See [Groundwork workflow](workflow/README.md) for the grouped review process and isolated offline runner:

```sh
node scripts/check-docs.mjs --report
.venv/bin/python scripts/verify-offline.py
```

The runner writes evidence to a temporary source copy rather than the repository and does not make live model calls. Its overall status is nonzero whenever either requested suite fails. The documentation checker is separate; it is not installed as a commit hook or remote CI gate. Existing local environment/ignore configuration is preserved.
