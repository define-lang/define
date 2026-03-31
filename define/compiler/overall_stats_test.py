from pathlib import PurePosixPath

from define.compiler import overall_stats
from define.compiler.validator import stats, validation_result


def _make_result(
    file_path: str,
    *,
    file_loading: int = 0,
    parse: int = 0,
    transform: int = 0,
    file_validation: int = 0,
    global_validation: int = 0,
    queue_wait: int = 0,
) -> validation_result.FileValidationResult:
    return validation_result.FileValidationResult(
        exception=None,
        source=None,
        file_path=PurePosixPath(file_path),
        root_prefix=PurePosixPath("."),
        stats=stats.ValidationTimingStats(
            file_loading=file_loading,
            parse=parse,
            transform=transform,
            file_validation=file_validation,
            global_validation=global_validation,
            queue_wait=queue_wait,
        ),
        file_diagnostics=[],
        definition_results=[],
    )


class TestFormatNs:
    def test_zero(self):
        assert overall_stats.format_ns(0) == "0.00 ms"

    def test_tiny_nonzero(self):
        assert overall_stats.format_ns(1) == "<0.01 ms"
        assert overall_stats.format_ns(4999) == "<0.01 ms"

    def test_exact_ms(self):
        assert overall_stats.format_ns(1_000_000) == "1.00 ms"

    def test_fractional_ms(self):
        assert overall_stats.format_ns(1_500_000) == "1.50 ms"

    def test_large_value(self):
        assert overall_stats.format_ns(123_456_789) == "123.46 ms"

    def test_boundary_rounds_to_001(self):
        assert overall_stats.format_ns(5000) == "0.01 ms"


class TestCalculateOverallStats:
    def test_single_file(self):
        results = [
            _make_result(
                "test.dfn",
                file_loading=100,
                parse=200,
                transform=300,
                file_validation=400,
                global_validation=50,
                queue_wait=25,
            )
        ]
        overall = overall_stats.calculate_overall_stats(
            results, config_loading_time_ns=500
        )
        assert overall.config_loading == 500
        assert overall.file_count == 1
        assert overall.file_loading == 100
        assert overall.parse == 200
        assert overall.transform == 300
        assert overall.file_validation == 400
        assert overall.global_validation == 50
        assert overall.avg_queue_wait == 25
        assert overall.max_queue_wait == 25
        assert overall.overall_compile == 100 + 200 + 300 + 400 + 50

    def test_multiple_files(self):
        results = [
            _make_result("a.dfn", parse=100, queue_wait=10),
            _make_result("b.dfn", parse=200, queue_wait=30),
        ]
        overall = overall_stats.calculate_overall_stats(
            results, config_loading_time_ns=0
        )
        assert overall.file_count == 2
        assert overall.parse == 300
        assert overall.avg_queue_wait == 20
        assert overall.max_queue_wait == 30

    def test_avg_queue_wait_truncates(self):
        results = [
            _make_result("a.dfn", queue_wait=10),
            _make_result("b.dfn", queue_wait=20),
            _make_result("c.dfn", queue_wait=20),
        ]
        overall = overall_stats.calculate_overall_stats(
            results, config_loading_time_ns=0
        )
        assert overall.avg_queue_wait == 16
        assert isinstance(overall.avg_queue_wait, int)

    def test_empty_results(self):
        overall = overall_stats.calculate_overall_stats([], config_loading_time_ns=100)
        assert overall.file_count == 0
        assert overall.avg_queue_wait == 0
        assert overall.config_loading == 100
        assert overall.overall_compile == 0


def _format(
    results: list[validation_result.FileValidationResult],
    config_loading_time_ns: int,
    mode: overall_stats.StatsMode,
) -> str:
    stats = overall_stats.calculate_overall_stats(results, config_loading_time_ns)
    return overall_stats.format_stats(stats, results, mode)


class TestFormatStatsOverall:
    def test_contains_sections(self):
        results = [_make_result("test.dfn", parse=5_000_000, transform=3_000_000)]
        output = _format(results, 1_000_000, overall_stats.StatsMode.OVERALL)
        assert "--- Compilation Stats ---" in output
        assert "-- Overall --" in output
        assert "-- Breakdown --" in output
        assert "-- Per File" not in output

    def test_shows_file_count(self):
        results = [_make_result("a.dfn"), _make_result("b.dfn")]
        output = _format(results, 0, overall_stats.StatsMode.OVERALL)
        assert "Files compiled:  2" in output

    def test_overall_section_includes_config_loading(self):
        results = [_make_result("test.dfn", parse=1_000_000)]
        output = _format(results, 2_000_000, overall_stats.StatsMode.OVERALL)
        overall_section = output[
            output.index("-- Overall --") : output.index("-- Breakdown --")
        ]
        assert "Config loading:  2.00 ms" in overall_section

    def test_shows_breakdown_labels(self):
        results = [_make_result("test.dfn", parse=1_000_000)]
        output = _format(results, 0, overall_stats.StatsMode.OVERALL)
        breakdown_section = output[output.index("-- Breakdown --") :]
        assert "Config loading:" not in breakdown_section
        assert "File loading:" in breakdown_section
        assert "Parse:" in breakdown_section
        assert "Transform:" in breakdown_section
        assert "File validation:" in breakdown_section
        assert "Global validation:" in breakdown_section

    def test_formats_overall_output_exactly(self):
        results = [
            _make_result(
                "test.dfn",
                file_loading=2_000_000,
                parse=5_000_000,
                transform=3_000_000,
                file_validation=4_000_000,
                global_validation=1_500_000,
                queue_wait=250_000,
            )
        ]
        output = _format(results, 1_000_000, overall_stats.StatsMode.OVERALL)
        assert output == (
            "--- Compilation Stats ---\n"
            "\n"
            "-- Overall --\n"
            " Files compiled:  1\n"
            "Overall compile:  15.50 ms\n"
            " Config loading:  1.00 ms\n"
            " Avg queue wait:  0.25 ms\n"
            " Max queue wait:  0.25 ms\n"
            "\n"
            "-- Breakdown --\n"
            "     File loading:  2.00 ms\n"
            "            Parse:  5.00 ms\n"
            "        Transform:  3.00 ms\n"
            "  File validation:  4.00 ms\n"
            "Global validation:  1.50 ms\n"
        )


class TestFormatStatsPerFile:
    def test_includes_per_file_section(self):
        results = [_make_result("test.dfn", parse=5_000_000)]
        output = _format(results, 0, overall_stats.StatsMode.PER_FILE)
        assert "-- Per File (slowest first) --" in output
        assert "test.dfn" in output

    def test_sorted_slowest_first(self):
        results = [
            _make_result("fast.dfn", parse=1_000_000),
            _make_result("slow.dfn", parse=10_000_000),
        ]
        output = _format(results, 0, overall_stats.StatsMode.PER_FILE)
        slow_pos = output.index("slow.dfn")
        fast_pos = output.index("fast.dfn")
        assert slow_pos < fast_pos

    def test_per_file_includes_all_phase_labels(self):
        results = [_make_result("test.dfn", parse=1_000_000)]
        output = _format(results, 0, overall_stats.StatsMode.PER_FILE)
        per_file_section = output[output.index("-- Per File") :]
        assert "File loading:" in per_file_section
        assert "Parse:" in per_file_section
        assert "Transform:" in per_file_section
        assert "File validation:" in per_file_section
        assert "Global validation:" in per_file_section
        assert "Queue wait:" in per_file_section
        assert "Overall compile:" in per_file_section

    def test_formats_per_file_output_exactly(self):
        results = [
            _make_result(
                "fast.dfn",
                file_loading=1_000_000,
                parse=2_000_000,
                transform=500_000,
                file_validation=500_000,
                global_validation=250_000,
                queue_wait=125_000,
            ),
            _make_result(
                "slow.dfn",
                file_loading=4_000_000,
                parse=8_000_000,
                transform=2_000_000,
                file_validation=3_000_000,
                global_validation=1_000_000,
                queue_wait=750_000,
            ),
        ]
        output = _format(results, 0, overall_stats.StatsMode.PER_FILE)
        assert output == (
            "--- Compilation Stats ---\n"
            "\n"
            "-- Overall --\n"
            " Files compiled:  2\n"
            "Overall compile:  22.25 ms\n"
            " Config loading:  0.00 ms\n"
            " Avg queue wait:  0.44 ms\n"
            " Max queue wait:  0.75 ms\n"
            "\n"
            "-- Breakdown --\n"
            "     File loading:  5.00 ms\n"
            "            Parse:  10.00 ms\n"
            "        Transform:  2.50 ms\n"
            "  File validation:  3.50 ms\n"
            "Global validation:  1.25 ms\n"
            "\n"
            "-- Per File (slowest first) --\n"
            "  slow.dfn\n"
            "      Overall compile:  18.00 ms\n"
            "         File loading:  4.00 ms\n"
            "                Parse:  8.00 ms\n"
            "            Transform:  2.00 ms\n"
            "      File validation:  3.00 ms\n"
            "    Global validation:  1.00 ms\n"
            "           Queue wait:  0.75 ms\n"
            "  fast.dfn\n"
            "      Overall compile:  4.25 ms\n"
            "         File loading:  1.00 ms\n"
            "                Parse:  2.00 ms\n"
            "            Transform:  0.50 ms\n"
            "      File validation:  0.50 ms\n"
            "    Global validation:  0.25 ms\n"
            "           Queue wait:  0.12 ms\n"
        )
