# LLM World Cup

[中文](README.md) · English

> **Alpha**: For a single question, 2 / 4 / 8 models answer once; an anonymous
> judge reviews each pair twice in a swapped A/B order and a knockout bracket
> picks this run's champion. The UI shows every answer, verdict reason, score
> and timing, and the full match report can be exported.

**Important boundary**: the champion only reflects preference for *this
question, this run* — it is **not** an overall model ranking and does not
support any procurement conclusion. Model outputs are stochastic, so the same
pairing can produce different results across runs.

---

## How it works

1. **Answer once**: each player answers the question exactly once; the answer
   is cached for the whole bracket.
2. **Anonymous double review**: each pair is judged twice with the A/B order
   swapped. A winner advances only when both verdicts point to the same
   candidate.
3. **No random champion**: ties, order disagreement, malformed judge output,
   or API failures stop the match at `needs_review` instead of picking a
   winner at random.
4. **Manual resume**: pick an advancer for each pending match in the UI; the
   bracket continues from the current round. Resume must reuse the original
   non-secret configuration (judge model, settings, rubric, players/models);
   only the API key environment variable may be re-supplied.
5. **Export**: each run saves JSON and Markdown under `.local/runs/`, and the UI
   also offers downloads.

## Requirements

- Python **3.11+** (development and CI cover 3.11 / 3.12 / 3.13)
- A reachable OpenAI-compatible Chat Completions endpoint (HTTPS remote, or a
  local model on `localhost`)
- Runtime dependency: `gradio==5.50.0` (`requirements.txt`); test and lint
  tools (`pytest`, `ruff`) are in `requirements-dev.txt`

## Install

Create an isolated virtualenv **inside this project directory** (do not reuse
a neighboring project's `.venv`):

```bash
git clone https://github.com/LYnini752/llm-worldcup.git
cd llm-worldcup
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

## Configuration

1. Copy `config.example.json` and edit it (the config box in the UI can be
   edited directly).
2. **Keys are injected only through environment variables**: put the variable
   name in the config, never a literal key:

```bash
export PROVIDER_KEY="sk-..."
# Different vendors may use different variable names
export ANOTHER_PROVIDER_KEY="..."
```

### Configuration fields

| Field | Description |
| --- | --- |
| `seed` | Integer seed that **only shuffles the bracket**; it does not control model randomness |
| `settings.temperature` | Player temperature, default `0.3` |
| `settings.max_tokens` | Player max output tokens, default `1500` |
| `settings.judge_temperature` | Judge temperature, default `0` |
| `settings.judge_max_tokens` | Judge max output tokens, default `1000` |
| `settings.timeout` | Per-request timeout in seconds, default `120` |
| `settings.retries` | Retries for transient errors (429 / 5xx / network timeout) and malformed judge verdicts, default `2` |
| `players[]` | Players: `name` (unique display name, no `||` or line breaks), `model`, `base_url`, `api_key_env` |
| `judge` | Judge model, same fields; `name` must not collide with a player name |
| `rubric` | Four weights, each 0–100 and totaling 100 |

One environment variable may serve several models. `base_url` must not carry a
username/password, query, or fragment; non-localhost URLs must use HTTPS.

## Run the UI

```bash
python app.py
# Default http://127.0.0.1:7861 ; set PORT to change the port
```

- Enter a question → edit the config → **Start match**.
- Without credentials, click **Offline synthetic preview** to view the UI
  sample (synthetic data, not real model performance).
- For pending matches, choose an advancer in the **Manual review** panel →
  **Submit decisions and resume**.
- **Load history** imports a previously exported JSON for viewing or further
  review.
- Exports are `.local/runs/<match-id>.json` and `.local/runs/<match-id>.md`.

## Tests and static checks

```bash
pip install -r requirements-dev.txt   # adds pytest, ruff for development/testing
python -m pytest -q
ruff check .
```

Tests use a stubbed callable and **make no real network request and read no
real keys**. They cover bracket rounds and answer caching, order-bias pause,
failure without a champion, manual resume, config validation, key isolation,
judgment retry, client retry and JSON parsing, export round-trip, injection
boundaries, path containment, atomic manual decisions, and resume-config
drift.

## Documentation

- [Architecture](docs/ARCHITECTURE.md): layers, match flow, report schema,
  security boundaries, extension points
- [Contributing](CONTRIBUTING.md): dev environment, local checks, code
  conventions
- [Security policy](SECURITY.md): key handling, untrusted-input boundary, known
  limits
- [Changelog](CHANGELOG.md), [Third-party notices](NOTICE.md),
  [Release checklist](docs/RELEASE.md)

## Security and privacy

- **No literal key** is written into config, source, logs, or exports; error
  messages never echo a key.
- Answer and judge text are treated as **untrusted data**: the judge system
  prompt instructs ignoring instructions, identity claims, or scoring demands
  inside answers; candidate answers enter only through the user payload JSON.
- `.env`, `config.json`, `.local/`, logs, and key files are excluded in
  `.gitignore` and do not enter version control.
- Apart from the model endpoints you configure yourself, this project uploads
  nothing to any third party; match records stay in the local `.local/`
  directory. Review your vendor's data retention and compliance policy.

## Demo data

`examples/demo_report.synthetic.json` / `.md` are hand-written fixtures marked
`"synthetic": true`; they do not represent any real model performance. Regenerate
them with:

```bash
.venv/bin/python examples/generate_demo.py
```

## Project structure

```
llm-worldcup/
├── app.py                  # Gradio UI: display, resume review, export entry
├── tournament.py           # Bracket: generation, double review, pause, resume
├── provider.py             # Dependency-free OpenAI-compatible client (retry/validate/mask)
├── exporter.py            # Report persistence and Markdown export
├── config.example.json     # Example config (keys via environment variable)
├── examples/               # Synthetic demo fixtures (marked synthetic)
├── docs/ARCHITECTURE.md    # Architecture and report schema notes
├── tests/                  # pytest unit / integration / security tests
├── .github/workflows/ci.yml# CI: test across Python versions + ruff
├── requirements.txt
├── requirements-dev.txt     # Extra dev dependencies (pytest, ruff)
├── pyproject.toml
├── CONTRIBUTING.md / SECURITY.md / CHANGELOG.md / NOTICE.md
├── LICENSE                 # MIT
└── .gitignore
```

## Known limitations (Alpha)

- No visual progress for concurrent judging; long brackets advance round by
  round.
- Judge scores are recorded only; there is no cross-bracket aggregate ranking.
- Only OpenAI-compatible Chat Completions; streaming is not enabled.
- Styles are injected via `Blocks(css=...)`; Gradio 6.0 removes that parameter,
  so style injection must be migrated on upgrade.
- Connection and read timeouts share a single `timeout` setting.
- New reports store a non-secret configuration digest to reject changed model identities, judge display name or endpoints on resume. Endpoints and keys are not exported. Legacy reports remain readable but cannot resume without this digest; start a new tournament. The digest is a consistency check, not proof of report authenticity.
- Real API connectivity, account quota, and the end-to-end real-model flow
  still need verification in a credentialed environment; this repository ships
  no real credentials.

## Verification status

Software alpha with automated coverage for brackets, paired judging, malformed imports, atomic manual review, export and configuration provenance. See repository Actions for Python 3.11–3.13 checks. The offline report is synthetic and makes no model request.

Real API connectivity, account quota and judging quality remain **untested**. The UI is currently Chinese; this English README covers setup and use.

## License

MIT; see [LICENSE](LICENSE). Third-party dependencies retain their own licenses.

## Included samples

See [sample data and attribution](examples/README.md) for ready-to-use inputs, offline previews, licenses, and limitations. No API credentials are included.
