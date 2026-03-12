# Savings Rate Scraping Agent

A Python agent that periodically scrapes savings product rates from UK fintech providers (Tembo, Chip, Moneybox) and stores them in JSON/CSV format for competitive analysis and historical tracking.

## Features

- **Multi-provider scraping**: Tembo, Chip, Moneybox
- **Rate extraction**: Configurable CSS selectors with fallback patterns
- **Storage backends**: JSON and CSV with schema versioning
- **Change detection**: Track rate changes and flag anomalies
- **Rate limiting**: Per-provider throttling with circuit breaker
- **CLI interface**: Easy-to-use command line tool
- **Cron support**: Scheduled scraping with logging

## Installation

```bash
# Clone repository
git clone <repo-url>
cd scraping-competitors

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium
```

## Usage

### CLI Commands

```bash
# Scrape all providers
python -m src.main scrape

# Scrape specific provider
python -m src.main scrape --provider tembo

# Output as CSV
python -m src.main scrape --format csv

# Enable change detection
python -m src.main scrape --detect-changes

# Show stored rates
python -m src.main show

# List providers
python -m src.main providers
```

### CLI Options

```
scrape:
  --provider, -p    Provider to scrape: all, tembo, chip, moneybox (default: all)
  --output, -o      Output file path (auto-generated if not provided)
  --format, -f      Output format: json, csv (default: json)
  --headless        Run browser in headless mode (default: true)
  --detect-changes  Compare with previous scrape and report changes
  -v, --verbose     Enable verbose logging

show:
  --format, -f      File format to show: json, csv (default: json)
  --input, -i       Input file path (default: data/rates_latest.{format})
```

## Scheduled Scraping

### Using Cron

```bash
# Edit crontab
crontab -e

# Run every 6 hours
0 */6 * * * /path/to/scraping-competitors/scripts/run_scraper.sh

# Run daily at 9am with change detection
0 9 * * * /path/to/scraping-competitors/scripts/run_scraper.sh --detect-changes

# Run hourly for specific provider
0 * * * * /path/to/scraping-competitors/scripts/run_scraper.sh --provider tembo
```

### Script Options

```bash
./scripts/run_scraper.sh [options]

Options:
  --provider PROVIDER  Scrape specific provider
  --format FORMAT      Output format (json, csv)
  --detect-changes     Enable change detection
  --verbose, -v        Verbose output
  --help, -h           Show help
```

## Project Structure

```
scraping-competitors/
├── src/
│   ├── main.py              # CLI entry point
│   ├── orchestrator.py      # Multi-provider orchestration
│   ├── models/
│   │   ├── types.py         # Enums: Provider, ProductName, etc.
│   │   └── rate.py          # SavingsRate pydantic model
│   ├── scrapers/
│   │   ├── base.py          # Abstract base scraper
│   │   ├── tembo.py         # Tembo scraper
│   │   ├── chip.py          # Chip scraper
│   │   └── moneybox.py      # Moneybox scraper
│   ├── storage/
│   │   ├── json_store.py    # JSON storage backend
│   │   └── csv_store.py     # CSV storage backend
│   ├── utils/
│   │   ├── browser.py       # Playwright browser manager
│   │   └── rate_limiter.py  # Rate limiting + circuit breaker
│   └── analysis/
│       └── change_detector.py  # Rate change + anomaly detection
├── config/
│   └── providers/           # YAML configs per provider
├── tests/
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   ├── e2e/                # End-to-end tests
│   └── fixtures/           # HTML fixtures
├── data/                   # Output directory (gitignored)
├── logs/                   # Log files (gitignored)
├── scripts/
│   └── run_scraper.sh      # Cron script
└── docs/
    └── adr/                # Architecture Decision Records
```

## Configuration

Provider configurations are in `config/providers/*.yaml`:

```yaml
# config/providers/tembo.yaml
provider: tembo
base_url: https://www.tembomoney.com

products:
  - name: tembo_cash_isa
    url: /savings/cash-isa
    product_type: cash_isa
    rate_type: variable
    selectors:
      rate: ".rate-value, .aer-rate"
```

## Development

### Running Tests

```bash
# All unit tests
pytest -m unit

# With coverage
pytest -m unit --cov=src --cov-report=term-missing

# Specific test file
pytest tests/unit/test_scrapers.py -v
```

### Type Checking

```bash
mypy src/
```

### Linting

```bash
ruff check src/
ruff check --fix src/  # Auto-fix
```

## Data Format

### JSON Output

```json
{
  "schema_version": "1.0",
  "rates": [
    {
      "provider": "tembo",
      "product_name": "tembo_cash_isa",
      "product_type": "cash_isa",
      "rate": "4.55",
      "rate_type": "variable",
      "scraped_at": "2026-03-12T10:00:00+00:00",
      "url": "https://www.tembomoney.com/savings/cash-isa"
    }
  ]
}
```

### CSV Output

```csv
provider,product_name,product_type,rate,rate_type,scraped_at,url,...
tembo,tembo_cash_isa,cash_isa,4.55,variable,2026-03-12T10:00:00+00:00,...
```

## Architecture Decisions

See `docs/adr/` for Architecture Decision Records:

- [ADR-001: Rate Limiter Thread Safety](docs/adr/001-rate-limiter-thread-safety.md)

## License

MIT
