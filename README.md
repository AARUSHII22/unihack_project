# ForgeCat

## UniHack Product Content Enrichment Engine

ForgeCat turns sparse distributor-catalog records into a 252-column delivery-format export. The project prioritizes supplied master data and controlled vocabularies, with uncertainty routed to human review.

## Features

- Ingests CSV/XLSX records containing MPN, raw description, brand fields, and manufacturer text.
- Cleans placeholder brands and identifies probable duplicate MPN groups.
- Resolves manufacturer/brand using lookup data and fuzzy matching.
- Classifies products into department, class, fine category, and classpath.
- Extracts attributes, standardizes UOMs and fractions, and normalizes fitting aliases.
- Builds invoice, mobile, short, long, retail, and marketing descriptions.
- Validates output, generates review/duplicate reports, and scores against ground truth.
- Includes a Streamlit dashboard and optional LLM description refinement.

## Pipeline

```text
Raw CSV/XLSX
  -> ingest and placeholder cleanup
  -> duplicate detection
  -> manufacturer / brand resolution
  -> taxonomy classification
  -> attributes, UOM, and fittings normalization
  -> descriptions and validation
  -> delivery CSV + review/duplicate/metric reports
```

The end-to-end orchestrator is `forgecat/pipeline.py`: `enrich_row()` processes one record and `run_pipeline()` processes a source file.

## Requirements

- Python 3.10 or later
- pip
- Optional: Anthropic or OpenAI API key for LLM refinement

```bash
python -m pip install -r requirements.txt
```

## Quick start

From the repository root:

```bash
# Rebuild lookup/seed data from the included samples (optional)
python scripts/generate_all_seeds.py

# Enrich the supplied 1,000-item sample and calculate metrics
python scripts/run_pipeline.py --score

# Run automated checks
pytest tests/ -q
```

The repository already includes sample CSVs and fallback seed data. Regenerate seeds after changing sample inputs or seed-generation logic.

## Command-line usage

```bash
python scripts/run_pipeline.py
python scripts/run_pipeline.py --input path/to/catalog.xlsx
python scripts/run_pipeline.py --limit 50
python scripts/run_pipeline.py --output output/my_delivery_format.csv --score
```

| Flag | Purpose |
| --- | --- |
| `--input PATH` | Source CSV/XLSX; defaults to the included sample input. |
| `--output PATH` | Delivery CSV destination; default: `output/enriched_delivery_format.csv`. |
| `--limit N` | Enrich only the first `N` records. |
| `--score` | Calculate and save ground-truth comparison metrics. |
| `--llm` | Enable optional LLM description refinement. |

## Dashboard

```bash
streamlit run app/streamlit_app.py
```

The dashboard supports CSV/XLSX uploads and presents field accuracy, LOV compliance, description-limit compliance, coverage, duplicate counts, review flags, per-row ground-truth differences, and a downloadable CSV.

## Data and reference files

| Location | Contents |
| --- | --- |
| `Unihack_ Sample Dataset - Input.csv` | 1,000-row source sample |
| `Unihack_ Expected Output - Delivery Format.csv` | Delivery schema and sample ground truth |
| `data/raw/` | Sample CSVs and optional official reference workbooks |
| `forgecat/seed/` | Fallback manufacturers, classpaths, UOMs, fittings, rules, and hero SKUs |

Official reference workbooks can be placed in `data/raw/` using names configured in `forgecat/config.py`. Supported master data includes UOM standards, decimal/fraction mappings, manufacturer/brand lists, UniCat LOVs, and fittings/faucets LOVs.

## Outputs

| File in `output/` | Description |
| --- | --- |
| `enriched_delivery_format.csv` | Delivery export; internal fields are omitted. |
| `review_queue.json` | Confidence and validation issues requiring review. |
| `duplicate_report.json` | Probable duplicate groups. |
| `metrics.json` | Ground-truth metrics from `--score`. |
| `import_stats.json` | Master-data index/import statistics. |

Asset fields use deterministic placeholders such as `{BRAND}_{MPN}.jpg`; verify them against real DAM assets before production use.

## Optional LLM enrichment

LLM use is disabled by default. Deterministic enrichment works without any API key. To enable LLM refinement, set a key in your environment or local `.env`:

```bash
# Anthropic (default)
ANTHROPIC_API_KEY=your_key
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514

# Or OpenAI
OPENAI_API_KEY=your_key
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini

python scripts/run_pipeline.py --llm --score
```

LLMs can replace description fields only. Candidate data, rules, validation, taxonomy, and final export remain application-controlled. Never commit API keys.

## Tests and scoring

```bash
pytest tests/ -q
```

The sample-data test suite does not require proprietary XLSX files. Scoring reports field-level agreement, LOV compliance, invoice/mobile description length compliance, manufacturer match rate, tier coverage, review count, and duplicate count.

## Project structure

```text
app/                    Streamlit interface
data/raw/               Samples and optional official references
forgecat/
  importers/            Reference-data readers
  seed/                 Versioned fallback lookups
  ingest.py             Input loading and cleanup
  dedup.py              Duplicate detection
  manufacturer.py       Manufacturer/brand resolution
  classification.py     Taxonomy classification
  attributes.py         Attribute and UOM normalization
  fittings.py           Fittings vocabulary mapping
  descriptions.py       Content generation
  validator.py          Review flags and validation
  scorer.py             Ground-truth evaluation
  pipeline.py           Orchestration
scripts/                CLI and seed-generation tools
tests/                  Sample-data test suite
```

## Configuration

Settings in `forgecat/config.py` are configurable through environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `CONFIDENCE_THRESHOLD` | `60` | Resolution/review threshold |
| `FULL_DEPTH_CATEGORIES` | `dishwasher,faucet` | Categories targeted for full-depth enrichment |
| `ENABLE_MANUFACTURER_FETCH` | `false` | Enables manufacturer-domain fetching |
| `LLM_PROVIDER` | `anthropic` | Optional LLM provider |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Anthropic model name |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |

## Review guidance

ForgeCat accelerates catalog processing; it does not replace product-data governance. Inspect review flags, validate generated asset references, and load current official master data before production use. A high score against the supplied sample demonstrates consistency with that sample, not universal coverage.

## License

No license was supplied with the archive. Add one before redistribution or external contributions.

