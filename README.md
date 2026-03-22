# Energy Audit Copilot MVP

Energy Audit Copilot is a Python and Streamlit MVP for utility-bill ingestion, expected-usage baselining, diagnostics, recommendations, carbon estimation, compliance screening, and PDF audit report export.

## Goals

- Centralize building, utility, and equipment inputs for an audit workflow
- Provide a Streamlit interface for analysts and internal users
- Establish clear module boundaries for data ingestion, domain modeling, and service orchestration
- Enable fast iteration on the MVP without committing to premature implementation details

## Current Status

This repository currently includes:

- Utility bill ingestion with schema validation, unit normalization, and monthly expansion
- Demo weather ingestion and monthly feature engineering
- Separate electricity and gas baseline models with heuristic fallback
- Diagnostics, recommendation ranking, emissions, compliance, and PDF report export
- A Streamlit dashboard that starts immediately from sample data

This repository does not yet include:

- Portfolio-scale multi-building workflows
- External weather APIs or utility integrations
- Production deployment configuration
- Fully calibrated savings, emissions, or compliance logic for regulatory filing

## Proposed Architecture

```text
Streamlit UI
    -> Dashboard orchestration
        -> Ingestion / weather / features
        -> Baselines / diagnostics / recommendations
        -> Emissions / compliance / reporting
```

## Repository Layout

```text
.
|-- docs/
|-- sample_data/
|-- src/
|   |-- auditcopilot/
|   |   |-- baselines/
|   |   |-- compliance/
|   |   |-- dashboard/
|   |   |-- diagnostics/
|   |   |-- emissions/
|   |   |-- features/
|   |   |-- ingestion/
|   |   |-- recommendations/
|   |   |-- reporting/
|   |   `-- weather/
|   `-- energy_audit_copilot/
|       |-- data/
|       |-- domain/
|       `-- ui/
`-- tests/
```

## Getting Started

### 1. Create and activate an environment

```bash
python -m venv .venv
source .venv/bin/activate
```

Or with Conda:

```bash
conda create -n data_driven python=3.11 -y
conda activate data_driven
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Streamlit app

```bash
streamlit run src/energy_audit_copilot/ui/streamlit_app.py
```

The app will start with demo data from [`sample_data/`](sample_data/) if no CSV is uploaded.

Optional runtime behavior:

- When a CSV is uploaded, the app attempts to fetch historical weather for the billing period from Open-Meteo and caches it locally under `.cache/open_meteo/`
- If Open-Meteo lookup fails, the app falls back to the bundled sample monthly weather

### 4. Run tests

```bash
pytest -q
```

## Sample Data

The [`sample_data/`](sample_data/) directory contains placeholder CSV files for:

- building metadata
- utility bills
- equipment inventory
- candidate energy conservation measures

See [`sample_data/SCHEMA.md`](sample_data/SCHEMA.md) for the intended column-level meaning.

## Utility Bill Input Schema

Utility bill ingestion is implemented in [`src/auditcopilot/ingestion/utility_bills.py`](src/auditcopilot/ingestion/utility_bills.py).

Accepted CSV columns:

- `billing_start`: required, parseable date
- `billing_end`: required, parseable date, must be on or after `billing_start`
- `utility_type`: required, currently `electricity` or `gas`
- `usage`: required, numeric consumption value
- `usage_unit`: required, normalized by utility type
- `cost`: required, numeric total cost for the billing period

Supported unit normalization:

- Electricity is normalized to `kwh` from `wh`, `kwh`, or `mwh`
- Gas is normalized to `therms` from `therm`, `therms`, `btu`, `kbtu`, `mmbtu`, `ccf`, or `mcf`

Billing periods that span multiple calendar months are prorated into monthly rows based on day count. The ingestion result returns:

- a clean pandas `DataFrame` with normalized `usage`, `usage_unit`, and `billing_month`
- structured validation messages with `level`, `code`, `message`, `row`, and `column`

## Weather And Features

Monthly weather support is implemented through a provider abstraction in [`src/auditcopilot/weather/providers.py`](src/auditcopilot/weather/providers.py), with normalization logic in [`src/auditcopilot/weather/monthly.py`](src/auditcopilot/weather/monthly.py).

Available behavior:

- `WeatherProvider` defines a modular weather interface independent from Streamlit
- `DemoMonthlyWeatherProvider` reads offline demo weather from [`sample_data/monthly_weather.csv`](sample_data/monthly_weather.csv)
- monthly weather normalization produces `billing_month`, `avg_temp`, `hdd`, and `cdd`

Feature engineering helpers live in [`src/auditcopilot/features/monthly_features.py`](src/auditcopilot/features/monthly_features.py) and add:

- `electric_kwh_per_sqft`
- `gas_therms_per_sqft`
- `month_index`
- season flags for winter, spring, summer, and fall
- `heating_season`
- `cooling_season`

## What The App Does

- Ingests utility bills from CSV or bundled sample data
- Normalizes electricity and gas usage and joins monthly weather
- Engineers monthly intensity and seasonality features
- Builds separate expected-usage baselines for electricity and gas
- Detects rule-based operational and performance diagnostics
- Maps diagnostics to ranked recommendations
- Calculates annual emissions and optional compliance status
- Exports a simple PDF audit report from the Streamlit app

## Limitations

- The MVP assumes electricity is already normalized to `kwh` and gas to `therms` after ingestion; other fuels are not yet modeled
- Demo weather is local sample data, not live weather observations
- Baseline models prioritize explainability over forecast accuracy
- Fallback baseline behavior uses simple weather normalization when history is limited
- Recommendation savings, carbon ranges, and payback notes are heuristic placeholders
- LL97 mode requires the user to provide the correct annual emissions limit; occupancy-specific logic and exemptions are not encoded
- The PDF export is intentionally simple and does not include embedded charts or branding
- The app currently focuses on a single-building workflow

## Development Conventions

- Keep business logic inside `services/` and `domain/`, not directly in the UI
- Treat `sample_data/` as non-production demo input
- Add tests alongside each new capability as the MVP expands
- Prefer small, composable modules over monolithic scripts

## Future Roadmap

1. Add live weather providers and utility tariff or interval-data integrations.
2. Replace heuristic recommendation ranges with calibrated project-level estimation logic.
3. Add multi-building portfolio analysis, benchmarking, and filtering.
4. Introduce richer baseline models and backtesting metrics.
5. Expand compliance coverage beyond the generic mode and LL97 screening.
6. Add chart-rich branded PDF exports and downloadable structured outputs.
7. Support authentication, persistence, and deployment-ready application packaging.

## Testing

The repository includes automated tests for ingestion, weather helpers, baseline fallback behavior, diagnostics, recommendation ranking, emissions/compliance, and PDF export under [`tests/`](tests/).

## License

Add the appropriate license for this project before external distribution.
