#!/bin/bash
# Savings Rate Scraper - Cron Script
#
# This script runs the savings rate scraper and stores results.
# It's designed to be run via cron for periodic rate collection.
#
# Usage:
#   ./scripts/run_scraper.sh [options]
#
# Options:
#   --provider PROVIDER  Scrape specific provider (tembo, chip, moneybox, all)
#   --format FORMAT      Output format (json, csv)
#   --detect-changes     Enable change detection and logging
#
# Cron Examples:
#   # Run every 6 hours
#   0 */6 * * * /path/to/scraping-competitors/scripts/run_scraper.sh
#
#   # Run daily at 9am, detect changes
#   0 9 * * * /path/to/scraping-competitors/scripts/run_scraper.sh --detect-changes
#
#   # Run hourly for tembo only
#   0 * * * * /path/to/scraping-competitors/scripts/run_scraper.sh --provider tembo

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"
LOG_DIR="$PROJECT_DIR/logs"
DATA_DIR="$PROJECT_DIR/data"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Default options
PROVIDER="all"
FORMAT="json"
DETECT_CHANGES=""
VERBOSE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --provider)
            PROVIDER="$2"
            shift 2
            ;;
        --format)
            FORMAT="$2"
            shift 2
            ;;
        --detect-changes)
            DETECT_CHANGES="--detect-changes"
            shift
            ;;
        --verbose|-v)
            VERBOSE="-v"
            shift
            ;;
        --help|-h)
            head -30 "$0" | grep -E "^#" | sed 's/^# *//'
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Ensure directories exist
mkdir -p "$LOG_DIR" "$DATA_DIR"

# Activate virtual environment
if [[ -f "$VENV_DIR/bin/activate" ]]; then
    source "$VENV_DIR/bin/activate"
else
    echo "Error: Virtual environment not found at $VENV_DIR"
    echo "Run: python3 -m venv .venv && pip install -e ."
    exit 1
fi

# Set output file based on format
OUTPUT_FILE="$DATA_DIR/rates_${TIMESTAMP}.${FORMAT}"
LATEST_FILE="$DATA_DIR/rates_latest.${FORMAT}"
LOG_FILE="$LOG_DIR/scrape_${TIMESTAMP}.log"

# Run scraper
echo "$(date -Iseconds) Starting scrape..."
echo "  Provider: $PROVIDER"
echo "  Format: $FORMAT"
echo "  Output: $OUTPUT_FILE"

python -m src.main $VERBOSE scrape \
    --provider "$PROVIDER" \
    --format "$FORMAT" \
    --output "$OUTPUT_FILE" \
    $DETECT_CHANGES \
    2>&1 | tee "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

# Update latest symlink/copy
if [[ $EXIT_CODE -eq 0 ]]; then
    cp "$OUTPUT_FILE" "$LATEST_FILE"
    echo "$(date -Iseconds) Scrape completed successfully"
    echo "  Output saved to: $OUTPUT_FILE"
    echo "  Latest updated: $LATEST_FILE"
else
    echo "$(date -Iseconds) Scrape failed with exit code $EXIT_CODE"
    echo "  See log: $LOG_FILE"
fi

# Cleanup old files (keep last 30 days)
find "$DATA_DIR" -name "rates_*.json" -mtime +30 -delete 2>/dev/null || true
find "$DATA_DIR" -name "rates_*.csv" -mtime +30 -delete 2>/dev/null || true
find "$LOG_DIR" -name "scrape_*.log" -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE
