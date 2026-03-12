"""Unit tests for CLI."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from src.main import cli


@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


@pytest.mark.unit
class TestCLIBasics:
    """Tests for basic CLI functionality."""

    def test_cli_help(self, runner):
        """CLI shows help."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Savings rate scraping agent" in result.output

    def test_cli_providers_command(self, runner):
        """providers command lists providers."""
        result = runner.invoke(cli, ["providers"])
        assert result.exit_code == 0
        assert "tembo" in result.output
        assert "chip" in result.output
        assert "moneybox" in result.output


@pytest.mark.unit
class TestScrapeCommand:
    """Tests for scrape command."""

    def test_scrape_help(self, runner):
        """scrape command shows help."""
        result = runner.invoke(cli, ["scrape", "--help"])
        assert result.exit_code == 0
        assert "--provider" in result.output
        assert "--format" in result.output
        assert "--output" in result.output

    def test_scrape_provider_choices(self, runner):
        """scrape command validates provider choices."""
        result = runner.invoke(cli, ["scrape", "--provider", "invalid"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output

    def test_scrape_format_choices(self, runner):
        """scrape command validates format choices."""
        result = runner.invoke(cli, ["scrape", "--format", "xml"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output


@pytest.mark.unit
class TestShowCommand:
    """Tests for show command."""

    def test_show_help(self, runner):
        """show command shows help."""
        result = runner.invoke(cli, ["show", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output
        assert "--input" in result.output

    def test_show_missing_file(self, runner, tmp_path):
        """show command handles missing file."""
        result = runner.invoke(
            cli, ["show", "--input", str(tmp_path / "nonexistent.json")]
        )
        assert result.exit_code != 0


@pytest.mark.unit
class TestVerboseFlag:
    """Tests for verbose flag."""

    def test_verbose_flag_accepted(self, runner):
        """CLI accepts verbose flag."""
        result = runner.invoke(cli, ["-v", "providers"])
        assert result.exit_code == 0


@pytest.mark.unit
class TestScrapeExecution:
    """Tests for scrape command execution with mocks."""

    @patch("src.main._run_scrape")
    def test_scrape_calls_orchestrator(self, mock_run, runner, tmp_path):
        """scrape command calls orchestrator."""
        # Create mock result
        from src.orchestrator import OrchestratorResult

        mock_result = OrchestratorResult(
            total_rates=5,
            successful_providers=3,
            failed_providers=0,
        )
        mock_run.return_value = mock_result

        output_file = tmp_path / "rates.json"
        result = runner.invoke(
            cli,
            ["scrape", "--output", str(output_file)],
        )

        # Should have called _run_scrape
        mock_run.assert_called_once()

    @patch("src.main._run_scrape")
    def test_scrape_reports_results(self, mock_run, runner, tmp_path):
        """scrape command reports results."""
        from src.orchestrator import OrchestratorResult

        mock_result = OrchestratorResult(
            total_rates=5,
            successful_providers=4,
            failed_providers=0,
        )
        mock_result.duration_seconds  # Access to trigger calculation
        mock_run.return_value = mock_result

        output_file = tmp_path / "rates.json"
        result = runner.invoke(
            cli,
            ["scrape", "--output", str(output_file)],
        )

        assert "Rates found: 5" in result.output
        assert "Providers scraped: 4/4" in result.output

    @patch("src.main._run_scrape")
    def test_scrape_single_provider(self, mock_run, runner, tmp_path):
        """scrape command filters to single provider."""
        from src.models.types import Provider
        from src.orchestrator import OrchestratorResult

        mock_result = OrchestratorResult(
            total_rates=2,
            successful_providers=1,
            failed_providers=0,
        )
        mock_run.return_value = mock_result

        output_file = tmp_path / "rates.json"
        result = runner.invoke(
            cli,
            ["scrape", "--provider", "tembo", "--output", str(output_file)],
        )

        # Check that only tembo was passed
        call_args = mock_run.call_args
        providers = call_args[0][0]
        assert len(providers) == 1
        assert providers[0] == Provider.TEMBO
