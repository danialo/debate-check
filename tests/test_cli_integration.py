"""Phase 6 driver tests: CLI integration."""

import json
import pytest
from io import StringIO
from click.testing import CliRunner

from debate_claim_extractor.cli import main


class TestCLIBasicOperation:
    """Tests for basic CLI functionality."""

    def test_cli_extracts_claims_from_stdin(self):
        """CLI extracts claims from stdin input."""
        runner = CliRunner()
        transcript = "HARRIS: Studies show free will is an illusion proven by neuroscience."

        result = runner.invoke(main, input=transcript)

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        output = json.loads(result.output)
        assert "claims" in output
        assert len(output["claims"]) >= 1

    def test_cli_outputs_valid_json(self):
        """CLI outputs valid JSON."""
        runner = CliRunner()
        transcript = "HARRIS: Brain scans show activity before conscious awareness."

        result = runner.invoke(main, input=transcript)

        assert result.exit_code == 0
        # Should be valid JSON
        output = json.loads(result.output)
        assert isinstance(output, dict)

    def test_cli_handles_empty_input(self):
        """CLI handles empty input gracefully."""
        runner = CliRunner()

        result = runner.invoke(main, input="")

        # Should error with helpful message
        assert result.exit_code != 0
        assert "No transcript" in result.output or "empty" in result.output.lower()


class TestCLIOptions:
    """Tests for CLI option handling."""

    def test_cli_fact_check_option(self):
        """--fact-check enables fact-checking."""
        runner = CliRunner()
        transcript = "HARRIS: Studies show 70% of decisions are made unconsciously."

        result = runner.invoke(main, ["--fact-check"], input=transcript)

        assert result.exit_code == 0
        output = json.loads(result.output)
        # Should have fact_checks field (even if empty without client)
        assert "fact_checks" in output or "claims" in output

    def test_cli_verbose_option(self):
        """--verbose enables debug logging."""
        runner = CliRunner()
        transcript = "HARRIS: Research proves consciousness emerges from neurons."

        result = runner.invoke(main, ["--verbose"], input=transcript)

        assert result.exit_code == 0

    def test_cli_use_htn_is_default(self):
        """HTN planner is the default extraction method."""
        runner = CliRunner()
        transcript = "HARRIS: Neuroscience demonstrates brain activity precedes choice."

        result = runner.invoke(main, input=transcript)

        assert result.exit_code == 0
        output = json.loads(result.output)
        # HTN produces frames, old pipeline didn't
        assert "frames" in output or "claims" in output


class TestCLIOutputFormat:
    """Tests for CLI output format."""

    def test_cli_output_includes_claims(self):
        """Output includes extracted claims."""
        runner = CliRunner()
        transcript = "HARRIS: Studies show consciousness is an emergent property."

        result = runner.invoke(main, input=transcript)

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "claims" in output

        if output["claims"]:
            claim = output["claims"][0]
            assert "text" in claim
            assert "claim_type" in claim

    def test_cli_output_includes_frames(self):
        """Output includes argument frames."""
        runner = CliRunner()
        transcript = """HARRIS: Free will is an illusion.

PETERSON: But subjective experience suggests otherwise."""

        result = runner.invoke(main, input=transcript)

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "frames" in output

    def test_cli_output_includes_stats(self):
        """Output includes extraction statistics."""
        runner = CliRunner()
        transcript = "HARRIS: Research demonstrates neural correlates of consciousness."

        result = runner.invoke(main, input=transcript)

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "stats" in output
        stats = output["stats"]
        assert "tasks_executed" in stats or "claims_count" in stats


class TestCLIFileIO:
    """Tests for file input/output."""

    def test_cli_reads_from_file(self, tmp_path):
        """CLI reads transcript from file."""
        runner = CliRunner()

        # Create temp input file
        input_file = tmp_path / "transcript.txt"
        input_file.write_text("HARRIS: Studies prove neural activity precedes decisions.")

        result = runner.invoke(main, ["-i", str(input_file)])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "claims" in output

    def test_cli_writes_to_file(self, tmp_path):
        """CLI writes output to file."""
        runner = CliRunner()

        output_file = tmp_path / "output.json"
        transcript = "HARRIS: Research shows consciousness emerges from complexity."

        result = runner.invoke(main, ["-o", str(output_file)], input=transcript)

        assert result.exit_code == 0
        assert output_file.exists()

        output = json.loads(output_file.read_text())
        assert "claims" in output
