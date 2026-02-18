#!/usr/bin/env python3
"""
Enterprise Test Report Generator with PDF Integration

This module generates comprehensive test reports using the PlanMaestro PDF Generator service.
It creates both HTML and PDF reports with detailed coverage analysis, performance metrics,
and visual charts for executive summaries.
"""

import hashlib
import json
import logging
import os
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import defusedxml.ElementTree as ET
import git
import psutil
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TestMetrics:
    """Test execution metrics."""

    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    error_tests: int = 0
    execution_time: float = 0.0
    coverage_percentage: float = 0.0
    performance_benchmarks: Dict[str, float] = None

    def __post_init__(self):
        if self.performance_benchmarks is None:
            self.performance_benchmarks = {}

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.failed_tests / self.total_tests) * 100


@dataclass
class TestCategory:
    """Test category breakdown."""

    name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    duration: float = 0.0
    coverage: float = 0.0
    avg_duration: float = 0.0
    slowest_test: str = ""
    fastest_test: str = ""
    flaky_tests: int = 0


@dataclass
class SystemMetrics:
    """System resource metrics during test execution."""

    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    memory_usage_percent: float = 0.0
    disk_io_read_mb: float = 0.0
    disk_io_write_mb: float = 0.0
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0
    load_average: List[float] = field(default_factory=list)


@dataclass
class CodeAnalytics:
    """Code repository analytics."""

    total_files: int = 0
    test_files: int = 0
    lines_of_code: int = 0
    lines_of_test_code: int = 0
    test_to_code_ratio: float = 0.0
    recent_commits: int = 0
    contributors: int = 0
    code_churn: float = 0.0  # Lines changed per commit
    complexity_score: float = 0.0
    technical_debt_minutes: float = 0.0


@dataclass
class TestVelocity:
    """Test execution velocity and trends."""

    total_execution_time: float = 0.0
    average_test_duration: float = 0.0
    slowest_tests: List[Dict[str, Any]] = field(default_factory=list)
    fastest_tests: List[Dict[str, Any]] = field(default_factory=list)
    performance_trend: str = "stable"  # improving, degrading, stable
    velocity_score: float = 0.0  # Tests per second
    parallelization_efficiency: float = 0.0


@dataclass
class QualityInsights:
    """Advanced quality insights and predictions."""

    stability_score: float = 0.0  # Based on failure patterns
    reliability_index: float = 0.0  # Historical success rate
    maintainability_score: float = 0.0
    risk_assessment: str = "low"  # low, medium, high
    flaky_test_percentage: float = 0.0
    test_distribution_balance: float = 0.0
    coverage_trend: str = "stable"
    predicted_issues: List[str] = field(default_factory=list)


@dataclass
class VisualizationData:
    """Data prepared for charts and graphs."""

    test_results_pie: Dict[str, int] = field(default_factory=dict)
    coverage_by_module: Dict[str, float] = field(default_factory=dict)
    performance_timeline: List[Dict[str, Any]] = field(default_factory=list)
    category_distribution: Dict[str, int] = field(default_factory=dict)
    trend_data: Dict[str, List[float]] = field(default_factory=dict)
    heatmap_data: List[List[float]] = field(default_factory=list)
    benchmark_comparison: Dict[str, float] = field(default_factory=dict)


@dataclass
class TestReport:
    """Complete test report data structure with advanced analytics."""

    project_name: str
    timestamp: str
    metrics: TestMetrics
    categories: List[TestCategory]
    coverage_details: Dict[str, Any]
    performance_data: Dict[str, Any]
    test_files: List[str]
    environment: Dict[str, str]
    quality_gates: Dict[str, bool]
    recommendations: List[str]
    # Enhanced analytics
    system_metrics: SystemMetrics = field(default_factory=SystemMetrics)
    code_analytics: CodeAnalytics = field(default_factory=CodeAnalytics)
    test_velocity: TestVelocity = field(default_factory=TestVelocity)
    quality_insights: QualityInsights = field(default_factory=QualityInsights)
    visualization_data: VisualizationData = field(default_factory=VisualizationData)


class TestReportGenerator:
    """Enterprise test report generator with PDF integration."""

    def __init__(
        self,
        project_name: str = "Test Suite",
        pdf_service_url: str = "http://localhost:4000",
    ):
        self.project_name = project_name
        self.pdf_service_url = pdf_service_url
        self.output_dir = Path("reports")
        self.output_dir.mkdir(exist_ok=True)

    def generate_report(self, run_tests: bool = True) -> Dict[str, str]:
        """
        Generate comprehensive test report with PDF output.

        Args:
            run_tests: Whether to run tests before generating report

        Returns:
            Dictionary with paths to generated reports
        """
        logger.info("🚀 Starting test report generation...")

        # Step 1: Run tests if requested
        if run_tests:
            self._run_tests()

        # Step 2: Collect test data
        test_data = self._collect_test_data()

        # Step 3: Generate report object
        report = self._build_report(test_data)

        # Step 4: Generate HTML report
        html_path = self._generate_html_report(report)

        # Step 5: Generate PDF report
        pdf_path = self._generate_pdf_report(report)

        # Step 6: Generate executive summary
        summary_path = self._generate_executive_summary(report)

        logger.info("✅ Test report generation completed!")

        return {
            "html_report": str(html_path),
            "pdf_report": str(pdf_path) if pdf_path else None,
            "executive_summary": str(summary_path) if summary_path else None,
            "json_data": str(self.output_dir / "test_data.json"),
        }

    def _run_tests(self) -> None:
        """Run the test suite with comprehensive reporting."""
        logger.info("🧪 Running test suite...")

        cmd = [
            "python",
            "-m",
            "pytest",
            "--cov=ice_pipeline",
            "--cov-report=xml:reports/coverage.xml",
            "--cov-report=json:reports/coverage.json",
            "--cov-report=html:reports/coverage",
            "--json-report",
            "--json-report-file=reports/test-results.json",
            "--html=reports/pytest-report.html",
            "--self-contained-html",
            "--benchmark-json=reports/benchmark.json",
            "-v",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            logger.info(
                f"Test execution completed with return code: {result.returncode}"
            )
        except subprocess.TimeoutExpired:
            logger.error("Test execution timed out after 5 minutes")
        except Exception as e:
            logger.error(f"Error running tests: {e}")

    def _collect_test_data(self) -> Dict[str, Any]:
        """Collect test execution data from various sources."""
        logger.info("📊 Collecting test data...")

        data = {
            "pytest_json": self._load_pytest_json(),
            "coverage_xml": self._load_coverage_xml(),
            "coverage_json": self._load_coverage_json(),
            "benchmark_json": self._load_benchmark_json(),
            "environment": self._get_environment_info(),
        }

        # Save raw data for debugging
        with open(self.output_dir / "test_data.json", "w") as f:
            json.dump(data, f, indent=2, default=str)

        return data

    def _convert_junit_to_pytest_format(self, root: ET.Element) -> Dict[str, Any]:
        """Convert JUnit XML to pytest-like JSON structure."""
        # Handle nested testsuite structure (JUnit XML can have <testsuites><testsuite>)
        testsuite = root
        if root.tag == "testsuites":
            # Find the first testsuite element
            testsuite = root.find("testsuite")
            if testsuite is None:
                testsuite = root

        total_tests = int(testsuite.get("tests", "0"))
        failures = int(testsuite.get("failures", "0"))
        errors = int(testsuite.get("errors", "0"))
        skipped = int(testsuite.get("skipped", "0"))
        duration = float(testsuite.get("time", "0.0"))

        passed = total_tests - failures - errors - skipped

        return {
            "summary": {
                "total": total_tests,
                "passed": passed,
                "failed": failures + errors,
                "error": errors,
                "skipped": skipped,
                "duration": duration,
            },
            "collectors": [],
            "tests": [],
        }

    def _load_pytest_json(self) -> Optional[Dict]:
        """Load pytest JSON report or JUnit XML as fallback."""
        # Try pytest JSON first
        try:
            with open(self.output_dir / "test-results.json") as f:
                return json.load(f)
        except FileNotFoundError:
            pass

        # Try JUnit XML as fallback
        try:
            junit_xml_path = self.output_dir / "unit-tests.xml"
            if junit_xml_path.exists():
                tree = ET.parse(junit_xml_path)
                root = tree.getroot()
                # Convert JUnit XML to basic pytest-like structure
                return self._convert_junit_to_pytest_format(root)
        except Exception as e:
            logger.warning(f"Error loading JUnit XML: {e}")

        logger.warning("pytest JSON report not found")
        return None

    def _load_coverage_xml(self) -> Optional[ET.Element]:
        """Load coverage XML report."""
        # Try main coverage.xml first
        try:
            tree = ET.parse(self.output_dir / "coverage.xml")
            return tree.getroot()
        except FileNotFoundError:
            pass

        # Try unit test coverage XML
        try:
            tree = ET.parse(self.output_dir / "coverage" / "unit-coverage.xml")
            return tree.getroot()
        except FileNotFoundError:
            logger.warning("Coverage XML report not found")
            return None

    def _load_coverage_json(self) -> Optional[Dict]:
        """Load coverage JSON report."""
        try:
            with open(self.output_dir / "coverage.json") as f:
                content = f.read().strip()
                if not content:
                    return None
                return json.loads(content)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Coverage JSON report not found or invalid: {e}")
            return None

    def _load_benchmark_json(self) -> Optional[Dict]:
        """Load benchmark JSON report."""
        try:
            with open(self.output_dir / "benchmark.json") as f:
                content = f.read().strip()
                if not content:
                    return None
                return json.loads(content)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Benchmark JSON report not found or invalid: {e}")
            return None

    def _get_environment_info(self) -> Dict[str, str]:
        """Get environment information."""
        return {
            "python_version": sys.version,
            "platform": sys.platform,
            "cwd": os.getcwd(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": os.getenv("USER", "unknown"),
            "ci_env": os.getenv("CI", "false"),
            "github_actions": os.getenv("GITHUB_ACTIONS", "false"),
        }

    def _build_report(self, data: Dict[str, Any]) -> TestReport:
        """Build comprehensive test report object."""
        logger.info("🔨 Building test report...")

        # Extract basic metrics from pytest data
        metrics = self._extract_metrics(data)
        categories = self._extract_categories(data)
        coverage_details = self._extract_coverage_details(data)
        performance_data = self._extract_performance_data(data)
        quality_gates = self._evaluate_quality_gates(metrics)

        # Collect advanced analytics
        system_metrics = self._collect_system_metrics()
        code_analytics = self._analyze_codebase()
        test_velocity = self._calculate_test_velocity(data, metrics)
        quality_insights = self._generate_quality_insights(metrics, categories)
        visualization_data = self._prepare_visualization_data(
            metrics, categories, coverage_details
        )

        # Generate enhanced recommendations
        recommendations = self._generate_enhanced_recommendations(
            metrics, quality_gates, quality_insights, code_analytics
        )

        return TestReport(
            project_name=self.project_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metrics=metrics,
            categories=categories,
            coverage_details=coverage_details,
            performance_data=performance_data,
            test_files=self._get_test_files(),
            environment=data["environment"],
            quality_gates=quality_gates,
            recommendations=recommendations,
            system_metrics=system_metrics,
            code_analytics=code_analytics,
            test_velocity=test_velocity,
            quality_insights=quality_insights,
            visualization_data=visualization_data,
        )

    def _extract_metrics(self, data: Dict[str, Any]) -> TestMetrics:
        """Extract test metrics from collected data."""
        pytest_data = data.get("pytest_json") or {}
        coverage_data = data.get("coverage_json") or {}

        # Handle None pytest_data
        if not pytest_data:
            pytest_data = {}

        summary = pytest_data.get("summary", {})

        # Extract coverage from XML if JSON not available
        coverage_percentage = 0.0
        if coverage_data:
            coverage_percentage = coverage_data.get("totals", {}).get(
                "percent_covered", 0.0
            )
        else:
            # Try to extract from coverage XML
            coverage_xml = data.get("coverage_xml")
            if coverage_xml is not None:
                coverage_percentage = self._extract_coverage_from_xml(coverage_xml)

        metrics = TestMetrics(
            total_tests=summary.get("total", 0),
            passed_tests=summary.get("passed", 0),
            failed_tests=summary.get("failed", 0),
            skipped_tests=summary.get("skipped", 0),
            error_tests=summary.get("error", 0),
            execution_time=summary.get("duration", 0.0),
            coverage_percentage=coverage_percentage,
        )

        # Extract performance benchmarks
        benchmark_data = data.get("benchmark_json", {})
        if benchmark_data:
            benchmarks = benchmark_data.get("benchmarks", [])
            metrics.performance_benchmarks = {
                bench["name"]: bench["stats"]["mean"] for bench in benchmarks
            }

        return metrics

    def _extract_coverage_from_xml(self, coverage_xml: ET.Element) -> float:
        """Extract coverage percentage from coverage XML."""
        try:
            # Coverage XML format: <coverage line-rate="0.78" ...>
            line_rate = coverage_xml.get("line-rate", "0.0")
            return float(line_rate) * 100.0
        except (ValueError, AttributeError):
            return 0.0

    def _extract_categories(self, data: Dict[str, Any]) -> List[TestCategory]:
        """Extract test categories breakdown."""
        categories = []
        pytest_data = data.get("pytest_json", {})

        # Group tests by markers/categories
        test_categories = {
            "unit": TestCategory("Unit Tests"),
            "integration": TestCategory("Integration Tests"),
            "api": TestCategory("API Tests"),
            "performance": TestCategory("Performance Tests"),
            "error_handling": TestCategory("Error Handling Tests"),
        }

        # Analyze test results by category
        tests = pytest_data.get("tests", [])
        for test in tests:
            markers = [marker.get("name", "") for marker in test.get("markers", [])]
            duration = test.get("duration", 0.0)
            outcome = test.get("outcome", "unknown")

            for marker in markers:
                if marker in test_categories:
                    category = test_categories[marker]
                    category.total += 1
                    category.duration += duration

                    if outcome == "passed":
                        category.passed += 1
                    elif outcome == "failed":
                        category.failed += 1

        # Add categories with tests
        categories = [cat for cat in test_categories.values() if cat.total > 0]

        # Add "Other" category for uncategorized tests
        categorized_total = sum(cat.total for cat in categories)
        total_tests = pytest_data.get("summary", {}).get("total", 0)

        if categorized_total < total_tests:
            other_category = TestCategory(
                name="Other Tests",
                total=total_tests - categorized_total,
                passed=pytest_data.get("summary", {}).get("passed", 0)
                - sum(cat.passed for cat in categories),
                failed=pytest_data.get("summary", {}).get("failed", 0)
                - sum(cat.failed for cat in categories),
            )
            categories.append(other_category)

        return categories

    def _extract_coverage_details(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract detailed coverage information."""
        coverage_data = data.get("coverage_json", {})

        if not coverage_data:
            return {}

        files_coverage = {}
        for file_path, file_data in coverage_data.get("files", {}).items():
            files_coverage[file_path] = {
                "statements": file_data.get("summary", {}).get("num_statements", 0),
                "missing": file_data.get("summary", {}).get("missing_lines", 0),
                "covered": file_data.get("summary", {}).get("covered_lines", 0),
                "percent": file_data.get("summary", {}).get("percent_covered", 0.0),
            }

        return {
            "total_coverage": coverage_data.get("totals", {}).get(
                "percent_covered", 0.0
            ),
            "files": files_coverage,
            "summary": coverage_data.get("totals", {}),
        }

    def _extract_performance_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract performance benchmark data."""
        benchmark_data = data.get("benchmark_json", {})

        if not benchmark_data:
            return {}

        benchmarks = []
        for bench in benchmark_data.get("benchmarks", []):
            benchmarks.append(
                {
                    "name": bench["name"],
                    "min": bench["stats"]["min"],
                    "max": bench["stats"]["max"],
                    "mean": bench["stats"]["mean"],
                    "stddev": bench["stats"]["stddev"],
                    "rounds": bench["stats"]["rounds"],
                }
            )

        return {
            "benchmarks": benchmarks,
            "machine_info": benchmark_data.get("machine_info", {}),
            "commit_info": benchmark_data.get("commit_info", {}),
        }

    def _get_test_files(self) -> List[str]:
        """Get list of test files."""
        test_files = []
        test_dirs = ["tests", "test"]

        for test_dir in test_dirs:
            if Path(test_dir).exists():
                for test_file in Path(test_dir).rglob("test_*.py"):
                    test_files.append(str(test_file))

        return test_files

    def _evaluate_quality_gates(self, metrics: TestMetrics) -> Dict[str, bool]:
        """Evaluate quality gates based on metrics."""
        return {
            "all_tests_passing": metrics.failed_tests == 0 and metrics.error_tests == 0,
            "coverage_threshold": metrics.coverage_percentage >= 78.0,
            "performance_acceptable": metrics.execution_time < 300.0,  # 5 minutes
            "pass_rate_acceptable": metrics.pass_rate >= 95.0,
            "no_critical_failures": metrics.error_tests == 0,
        }

    def _generate_recommendations(
        self, metrics: TestMetrics, gates: Dict[str, bool]
    ) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []

        if not gates["all_tests_passing"]:
            recommendations.append(
                f"🔴 Fix {metrics.failed_tests + metrics.error_tests} failing tests"
            )

        if not gates["coverage_threshold"]:
            recommendations.append(
                f"📊 Increase test coverage from {metrics.coverage_percentage:.1f}% to 78%+"
            )

        if not gates["performance_acceptable"]:
            recommendations.append(
                f"⚡ Optimize test execution time (currently {metrics.execution_time:.1f}s)"
            )

        if metrics.skipped_tests > 0:
            recommendations.append(f"⚠️ Review {metrics.skipped_tests} skipped tests")

        if gates["all_tests_passing"] and gates["coverage_threshold"]:
            recommendations.append(
                "✅ Excellent test suite! Consider adding more integration tests"
            )

        return recommendations

    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system resource metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()
            network = psutil.net_io_counters()
            load_avg = (
                list(psutil.getloadavg())
                if hasattr(psutil, "getloadavg")
                else [0.0, 0.0, 0.0]
            )

            return SystemMetrics(
                cpu_usage_percent=cpu_percent,
                memory_usage_mb=memory.used / (1024 * 1024),
                memory_usage_percent=memory.percent,
                disk_io_read_mb=(disk_io.read_bytes if disk_io else 0) / (1024 * 1024),
                disk_io_write_mb=(disk_io.write_bytes if disk_io else 0)
                / (1024 * 1024),
                network_sent_mb=(network.bytes_sent if network else 0) / (1024 * 1024),
                network_recv_mb=(network.bytes_recv if network else 0) / (1024 * 1024),
                load_average=load_avg,
            )
        except Exception as e:
            logger.warning(f"Failed to collect system metrics: {e}")
            return SystemMetrics()

    def _analyze_codebase(self) -> CodeAnalytics:
        """Analyze codebase for comprehensive metrics."""
        try:
            analytics = CodeAnalytics()

            # Count files and lines of code
            total_files = 0
            test_files = 0
            total_lines = 0
            test_lines = 0

            # Analyze Python files
            for py_file in Path(".").rglob("*.py"):
                if any(
                    excluded in str(py_file)
                    for excluded in ["venv", "__pycache__", ".git", "node_modules"]
                ):
                    continue

                total_files += 1

                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        line_count = len(
                            [
                                l
                                for l in lines
                                if l.strip() and not l.strip().startswith("#")
                            ]
                        )
                        total_lines += line_count

                        if "test" in str(py_file).lower() or py_file.name.startswith(
                            "test_"
                        ):
                            test_files += 1
                            test_lines += line_count
                except Exception:
                    continue

            analytics.total_files = total_files
            analytics.test_files = test_files
            analytics.lines_of_code = total_lines
            analytics.lines_of_test_code = test_lines
            analytics.test_to_code_ratio = (
                test_lines / max(total_lines - test_lines, 1)
            ) * 100

            # Git analysis
            try:
                repo = git.Repo(".")
                commits = list(repo.iter_commits(max_count=50))
                analytics.recent_commits = len(commits)
                analytics.contributors = len(
                    set(commit.author.email for commit in commits)
                )

                # Calculate code churn (simplified)
                if commits:
                    total_changes = 0
                    for commit in commits[:10]:  # Last 10 commits
                        try:
                            stats = commit.stats.total
                            total_changes += stats["insertions"] + stats["deletions"]
                        except:
                            continue
                    analytics.code_churn = total_changes / max(len(commits[:10]), 1)
            except Exception as e:
                logger.warning(f"Git analysis failed: {e}")

            # Complexity and technical debt (simplified)
            analytics.complexity_score = min(
                100.0, analytics.lines_of_code / 100
            )  # Simplified
            analytics.technical_debt_minutes = max(
                0, (100 - analytics.test_to_code_ratio) * 2
            )

            return analytics
        except Exception as e:
            logger.warning(f"Codebase analysis failed: {e}")
            return CodeAnalytics()

    def _calculate_test_velocity(
        self, data: Dict[str, Any], metrics: TestMetrics
    ) -> TestVelocity:
        """Calculate test execution velocity and performance metrics."""
        try:
            velocity = TestVelocity()
            velocity.total_execution_time = metrics.execution_time
            velocity.average_test_duration = metrics.execution_time / max(
                metrics.total_tests, 1
            )
            velocity.velocity_score = metrics.total_tests / max(
                metrics.execution_time, 0.1
            )

            # Analyze performance data
            benchmark_data = data.get("benchmark_json", {})
            if benchmark_data and "benchmarks" in benchmark_data:
                benchmarks = benchmark_data["benchmarks"]

                # Sort by duration to find slowest/fastest
                sorted_benchmarks = sorted(
                    benchmarks,
                    key=lambda x: x.get("stats", {}).get("mean", 0),
                    reverse=True,
                )

                # Top 5 slowest tests
                velocity.slowest_tests = [
                    {
                        "name": b["name"],
                        "duration": b["stats"]["mean"],
                        "rounds": b["stats"]["rounds"],
                    }
                    for b in sorted_benchmarks[:5]
                ]

                # Top 5 fastest tests
                velocity.fastest_tests = [
                    {
                        "name": b["name"],
                        "duration": b["stats"]["mean"],
                        "rounds": b["stats"]["rounds"],
                    }
                    for b in sorted_benchmarks[-5:]
                ]

            # Determine performance trend (simplified)
            if velocity.average_test_duration < 0.1:
                velocity.performance_trend = "excellent"
            elif velocity.average_test_duration < 0.5:
                velocity.performance_trend = "good"
            elif velocity.average_test_duration < 2.0:
                velocity.performance_trend = "acceptable"
            else:
                velocity.performance_trend = "needs_improvement"

            # Parallelization efficiency (simplified)
            ideal_time = velocity.total_execution_time / max(psutil.cpu_count(), 1)
            velocity.parallelization_efficiency = min(
                100.0, (ideal_time / max(velocity.total_execution_time, 0.1)) * 100
            )

            return velocity
        except Exception as e:
            logger.warning(f"Test velocity calculation failed: {e}")
            return TestVelocity()

    def _generate_quality_insights(
        self, metrics: TestMetrics, categories: List[TestCategory]
    ) -> QualityInsights:
        """Generate advanced quality insights and predictions."""
        try:
            insights = QualityInsights()

            # Stability score based on pass rate
            insights.stability_score = metrics.pass_rate
            insights.reliability_index = metrics.pass_rate

            # Test distribution balance
            if categories:
                category_sizes = [cat.total for cat in categories]
                max_category = max(category_sizes)
                min_category = min(category_sizes)
                insights.test_distribution_balance = (
                    min_category / max(max_category, 1)
                ) * 100

            # Risk assessment
            if metrics.pass_rate >= 95 and metrics.coverage_percentage >= 80:
                insights.risk_assessment = "low"
            elif metrics.pass_rate >= 85 and metrics.coverage_percentage >= 60:
                insights.risk_assessment = "medium"
            else:
                insights.risk_assessment = "high"

            # Maintainability score (combination of factors)
            coverage_factor = min(100, metrics.coverage_percentage)
            test_factor = min(100, (metrics.total_tests / 10) * 10)  # 10+ tests = good
            insights.maintainability_score = coverage_factor * 0.6 + test_factor * 0.4

            # Coverage trend (simplified)
            if metrics.coverage_percentage >= 80:
                insights.coverage_trend = "excellent"
            elif metrics.coverage_percentage >= 60:
                insights.coverage_trend = "good"
            else:
                insights.coverage_trend = "needs_improvement"

            # Predicted issues
            if metrics.failed_tests > 0:
                insights.predicted_issues.append(
                    f"Test failures may indicate unstable code areas"
                )
            if metrics.coverage_percentage < 70:
                insights.predicted_issues.append(
                    f"Low coverage increases risk of undetected bugs"
                )
            if metrics.execution_time > 120:  # 2 minutes
                insights.predicted_issues.append(
                    f"Long test execution may slow development cycle"
                )

            return insights
        except Exception as e:
            logger.warning(f"Quality insights generation failed: {e}")
            return QualityInsights()

    def _prepare_visualization_data(
        self,
        metrics: TestMetrics,
        categories: List[TestCategory],
        coverage: Dict[str, Any],
    ) -> VisualizationData:
        """Prepare data for charts and visualizations."""
        try:
            viz_data = VisualizationData()

            # Test results pie chart data
            viz_data.test_results_pie = {
                "passed": metrics.passed_tests,
                "failed": metrics.failed_tests,
                "skipped": metrics.skipped_tests,
                "error": metrics.error_tests,
            }

            # Category distribution
            viz_data.category_distribution = {cat.name: cat.total for cat in categories}

            # Coverage by module
            if coverage.get("files"):
                viz_data.coverage_by_module = {
                    Path(file_path).stem: file_data.get("percent", 0)
                    for file_path, file_data in coverage["files"].items()
                }

            # Performance timeline (simplified)
            viz_data.performance_timeline = [
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "execution_time": metrics.execution_time,
                    "pass_rate": metrics.pass_rate,
                    "coverage": metrics.coverage_percentage,
                }
            ]

            # Trend data for charts
            viz_data.trend_data = {
                "pass_rate_trend": [metrics.pass_rate],
                "coverage_trend": [metrics.coverage_percentage],
                "execution_time_trend": [metrics.execution_time],
            }

            # Benchmark comparison
            if metrics.performance_benchmarks:
                viz_data.benchmark_comparison = metrics.performance_benchmarks

            return viz_data
        except Exception as e:
            logger.warning(f"Visualization data preparation failed: {e}")
            return VisualizationData()

    def _generate_enhanced_recommendations(
        self,
        metrics: TestMetrics,
        gates: Dict[str, bool],
        insights: QualityInsights,
        analytics: CodeAnalytics,
    ) -> List[str]:
        """Generate enhanced recommendations based on comprehensive analysis."""
        recommendations = []

        # Test coverage recommendations
        if not gates["coverage_threshold"]:
            gap = 78 - metrics.coverage_percentage
            recommendations.append(
                f"🎯 Priority: Increase test coverage by {gap:.1f}% (currently {metrics.coverage_percentage:.1f}%)"
            )
            recommendations.append(
                f"💡 Focus on modules with lowest coverage: {', '.join(list(insights.predicted_issues)[:2])}"
            )

        # Performance recommendations
        if metrics.execution_time > 60:  # 1 minute
            recommendations.append(
                f"⚡ Optimize test execution time (currently {metrics.execution_time:.1f}s)"
            )
            recommendations.append(
                f"🔧 Consider parallel test execution to improve velocity"
            )

        # Code quality recommendations
        if analytics.test_to_code_ratio < 50:
            recommendations.append(
                f"📊 Increase test-to-code ratio (currently {analytics.test_to_code_ratio:.1f}%)"
            )

        # Technical debt recommendations
        if analytics.technical_debt_minutes > 30:
            recommendations.append(
                f"🔨 Address technical debt (~{analytics.technical_debt_minutes:.0f} minutes estimated)"
            )

        # Risk-based recommendations
        if insights.risk_assessment == "high":
            recommendations.append(
                f"⚠️  High-risk assessment: Immediate attention needed for test stability"
            )
            recommendations.append(
                f"🛡️ Implement additional integration and regression tests"
            )

        # Performance insights
        if insights.stability_score < 90:
            recommendations.append(
                f"📈 Improve test stability (current score: {insights.stability_score:.1f}%)"
            )

        # Success recommendations
        if (
            gates["all_tests_passing"]
            and gates["coverage_threshold"]
            and insights.risk_assessment == "low"
        ):
            recommendations.append(
                "✅ Excellent test suite! Consider adding mutation testing"
            )
            recommendations.append(
                "🎯 Explore property-based testing for edge case discovery"
            )
            recommendations.append("📊 Set up performance regression detection")

        # Analytics-driven recommendations
        if analytics.recent_commits > 20:
            recommendations.append(
                f"🔄 High commit velocity detected - ensure test automation keeps pace"
            )

        if len(recommendations) == 0:
            recommendations.append(
                "🎉 Test suite is performing excellently across all metrics!"
            )

        return recommendations

    def _generate_html_report(self, report: TestReport) -> Path:
        """Generate comprehensive HTML report."""
        logger.info("📄 Generating HTML report...")

        html_content = self._build_html_template(report)
        html_path = self.output_dir / "comprehensive_test_report.html"

        with open(html_path, "w") as f:
            f.write(html_content)

        logger.info(f"HTML report saved to: {html_path}")
        return html_path

    def _build_html_template(self, report: TestReport) -> str:
        """Build HTML template for the report."""
        status_icon = "✅" if report.quality_gates["all_tests_passing"] else "❌"
        status_class = (
            "success" if report.quality_gates["all_tests_passing"] else "failure"
        )

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🏢 {report.project_name} - Enterprise Test Analytics Report</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .header .timestamp {{
            opacity: 0.9;
            margin-top: 10px;
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            margin: 10px 0;
            font-weight: bold;
        }}
        .success {{
            background-color: #4CAF50;
            color: white;
        }}
        .failure {{
            background-color: #f44336;
            color: white;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
        }}
        .metric-card {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            border-left: 4px solid #667eea;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        .metric-label {{
            color: #666;
            margin-top: 5px;
        }}
        .section {{
            padding: 20px 30px;
            border-bottom: 1px solid #eee;
        }}
        .section h2 {{
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        .category-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
        }}
        .category-card {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
        }}
        .coverage-bar {{
            background: #e0e0e0;
            border-radius: 10px;
            height: 20px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .coverage-fill {{
            height: 100%;
            background: linear-gradient(90deg, #ff4444, #ffaa00, #44ff44);
            transition: width 0.3s ease;
        }}
        .recommendations {{
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 8px;
            padding: 20px;
        }}
        .recommendation {{
            margin: 10px 0;
            padding: 10px;
            background: white;
            border-radius: 5px;
        }}
        .quality-gates {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        .gate {{
            padding: 10px;
            border-radius: 5px;
            text-align: center;
        }}
        .gate.pass {{
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }}
        .gate.fail {{
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
        }}
        .performance-chart {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{status_icon} {report.project_name}</h1>
            <div class="status-badge {status_class}">
                {'All Tests Passing' if report.quality_gates['all_tests_passing'] else 'Tests Failed'}
            </div>
            <div class="timestamp">Generated: {report.timestamp}</div>
        </div>
        
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-value">{report.metrics.total_tests}</div>
                <div class="metric-label">Total Tests</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{report.metrics.passed_tests}</div>
                <div class="metric-label">Passed</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{report.metrics.failed_tests}</div>
                <div class="metric-label">Failed</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{report.metrics.coverage_percentage:.1f}%</div>
                <div class="metric-label">Coverage</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{report.metrics.execution_time:.1f}s</div>
                <div class="metric-label">Execution Time</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{report.metrics.pass_rate:.1f}%</div>
                <div class="metric-label">Pass Rate</div>
            </div>
        </div>
        
        {self._generate_enhanced_metrics_html(report)}
        
        <div class="section">
            <h2>🎯 Quality Gates</h2>
            <div class="quality-gates">
                {self._generate_quality_gates_html(report.quality_gates)}
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Test Categories</h2>
            <div class="category-grid">
                {self._generate_categories_html(report.categories)}
            </div>
        </div>
        
        <div class="section">
            <h2>📈 Coverage Details</h2>
            <div class="coverage-bar">
                <div class="coverage-fill" style="width: {report.metrics.coverage_percentage}%"></div>
            </div>
            <p>Overall Coverage: <strong>{report.metrics.coverage_percentage:.2f}%</strong></p>
            {self._generate_coverage_table_html(report.coverage_details)}
        </div>
        
        {self._generate_performance_section_html(report.performance_data)}
        
        <div class="section">
            <h2>💡 Recommendations</h2>
            <div class="recommendations">
                {self._generate_recommendations_html(report.recommendations)}
            </div>
        </div>
        
        <div class="section">
            <h2>🔧 Environment</h2>
            <table>
                <tr><th>Python Version</th><td>{report.environment.get('python_version', 'N/A')}</td></tr>
                <tr><th>Platform</th><td>{report.environment.get('platform', 'N/A')}</td></tr>
                <tr><th>Working Directory</th><td>{report.environment.get('cwd', 'N/A')}</td></tr>
                <tr><th>CI Environment</th><td>{report.environment.get('ci_env', 'N/A')}</td></tr>
            </table>
        </div>
    </div>
</body>
</html>
        """

    def _generate_enhanced_metrics_html(self, report: TestReport) -> str:
        """Generate HTML for enhanced analytics sections."""
        return f"""
        <div class="section">
            <h2>🖥️ System Performance</h2>
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-value">{report.system_metrics.cpu_usage_percent:.1f}%</div>
                    <div class="metric-label">CPU Usage</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.system_metrics.memory_usage_mb:.0f}MB</div>
                    <div class="metric-label">Memory Used</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.system_metrics.memory_usage_percent:.1f}%</div>
                    <div class="metric-label">Memory %</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.system_metrics.load_average[0]:.2f}</div>
                    <div class="metric-label">Load Average</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Code Analytics</h2>
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-value">{report.code_analytics.total_files}</div>
                    <div class="metric-label">Total Files</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.code_analytics.test_files}</div>
                    <div class="metric-label">Test Files</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.code_analytics.lines_of_code:,}</div>
                    <div class="metric-label">Lines of Code</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.code_analytics.test_to_code_ratio:.1f}%</div>
                    <div class="metric-label">Test to Code Ratio</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.code_analytics.recent_commits}</div>
                    <div class="metric-label">Recent Commits</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.code_analytics.technical_debt_minutes:.0f}min</div>
                    <div class="metric-label">Technical Debt</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>⚡ Test Velocity & Performance</h2>
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-value">{report.test_velocity.velocity_score:.1f}</div>
                    <div class="metric-label">Tests per Second</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.test_velocity.average_test_duration*1000:.0f}ms</div>
                    <div class="metric-label">Avg Test Duration</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.test_velocity.performance_trend.title()}</div>
                    <div class="metric-label">Performance Trend</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.test_velocity.parallelization_efficiency:.1f}%</div>
                    <div class="metric-label">Parallelization Efficiency</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>📈 Quality Insights</h2>
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-value" style="color: {'#4CAF50' if report.quality_insights.risk_assessment == 'low' else '#ff9800' if report.quality_insights.risk_assessment == 'medium' else '#f44336'}">{report.quality_insights.risk_assessment.upper()}</div>
                    <div class="metric-label">Risk Assessment</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.quality_insights.stability_score:.1f}</div>
                    <div class="metric-label">Stability Score</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.quality_insights.maintainability_score:.1f}</div>
                    <div class="metric-label">Maintainability</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.quality_insights.coverage_trend.replace('_', ' ').title()}</div>
                    <div class="metric-label">Coverage Trend</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.quality_insights.reliability_index:.1f}%</div>
                    <div class="metric-label">Reliability Index</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{report.quality_insights.test_distribution_balance:.1f}%</div>
                    <div class="metric-label">Test Balance</div>
                </div>
            </div>
        </div>
        """

    def _generate_quality_gates_html(self, gates: Dict[str, bool]) -> str:
        """Generate HTML for quality gates."""
        html = ""
        gate_names = {
            "all_tests_passing": "All Tests Passing",
            "coverage_threshold": "Coverage Threshold",
            "performance_acceptable": "Performance Acceptable",
            "pass_rate_acceptable": "Pass Rate Acceptable",
            "no_critical_failures": "No Critical Failures",
        }

        for gate, passed in gates.items():
            status_class = "pass" if passed else "fail"
            icon = "✅" if passed else "❌"
            html += f"""
            <div class="gate {status_class}">
                {icon} {gate_names.get(gate, gate.replace('_', ' ').title())}
            </div>
            """

        return html

    def _generate_categories_html(self, categories: List[TestCategory]) -> str:
        """Generate HTML for test categories."""
        html = ""
        for category in categories:
            pass_rate = (
                (category.passed / category.total * 100) if category.total > 0 else 0
            )
            html += f"""
            <div class="category-card">
                <h3>{category.name}</h3>
                <p><strong>Total:</strong> {category.total}</p>
                <p><strong>Passed:</strong> {category.passed}</p>
                <p><strong>Failed:</strong> {category.failed}</p>
                <p><strong>Pass Rate:</strong> {pass_rate:.1f}%</p>
                <p><strong>Duration:</strong> {category.duration:.2f}s</p>
            </div>
            """
        return html

    def _generate_coverage_table_html(self, coverage: Dict[str, Any]) -> str:
        """Generate HTML table for coverage details."""
        if not coverage.get("files"):
            return "<p>No coverage data available</p>"

        html = "<table><tr><th>File</th><th>Statements</th><th>Missing</th><th>Coverage</th></tr>"

        for file_path, file_data in coverage["files"].items():
            file_name = Path(file_path).name
            html += f"""
            <tr>
                <td>{file_name}</td>
                <td>{file_data['statements']}</td>
                <td>{file_data['missing']}</td>
                <td>{file_data['percent']:.1f}%</td>
            </tr>
            """

        html += "</table>"
        return html

    def _generate_performance_section_html(self, performance: Dict[str, Any]) -> str:
        """Generate HTML for performance section."""
        if not performance.get("benchmarks"):
            return ""

        html = """
        <div class="section">
            <h2>⚡ Performance Benchmarks</h2>
            <div class="performance-chart">
        """

        for benchmark in performance["benchmarks"]:
            html += f"""
            <div style="margin: 15px 0;">
                <strong>{benchmark['name']}</strong><br>
                Mean: {benchmark['mean']:.3f}s | 
                Min: {benchmark['min']:.3f}s | 
                Max: {benchmark['max']:.3f}s | 
                Rounds: {benchmark['rounds']}
            </div>
            """

        html += """
            </div>
        </div>
        """

        return html

    def _generate_recommendations_html(self, recommendations: List[str]) -> str:
        """Generate HTML for recommendations."""
        if not recommendations:
            return "<p>✅ No recommendations - your test suite looks great!</p>"

        html = ""
        for rec in recommendations:
            html += f'<div class="recommendation">{rec}</div>'

        return html

    def _generate_pdf_report(self, report: TestReport) -> Optional[Path]:
        """Generate PDF report using the PDF service."""
        logger.info("📄 Generating PDF report...")

        try:
            # Prepare data for PDF generation
            pdf_data = self._prepare_pdf_data(report)

            # Call PDF generation service
            response = requests.post(
                f"{self.pdf_service_url}/api/pdf/generate-sync",
                json={
                    "templateId": "test-report",
                    "data": pdf_data,
                    "returnBuffer": False,
                    "format": "A4",
                    "printBackground": True,
                },
                timeout=120,
            )

            if response.status_code == 200:
                # PDF generated successfully
                pdf_path = self.output_dir / "test_report.pdf"

                if response.headers.get("content-type") == "application/pdf":
                    # Direct PDF response
                    with open(pdf_path, "wb") as f:
                        f.write(response.content)
                else:
                    # JSON response with download info
                    result = response.json()
                    if result.get("success"):
                        logger.info("PDF generated successfully via service")
                        return pdf_path

                logger.info(f"PDF report saved to: {pdf_path}")
                return pdf_path
            else:
                logger.error(f"PDF generation failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None

        except requests.RequestException as e:
            logger.warning(f"PDF service not available: {e}")
            logger.info("Falling back to HTML-to-PDF conversion...")
            return self._fallback_pdf_generation(report)
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            return None

    def _prepare_pdf_data(self, report: TestReport) -> Dict[str, Any]:
        """Prepare data for PDF generation."""
        return {
            "title": f"{report.project_name} - Test Report",
            "timestamp": report.timestamp,
            "summary": {
                "total_tests": report.metrics.total_tests,
                "passed_tests": report.metrics.passed_tests,
                "failed_tests": report.metrics.failed_tests,
                "coverage": f"{report.metrics.coverage_percentage:.1f}%",
                "pass_rate": f"{report.metrics.pass_rate:.1f}%",
                "execution_time": f"{report.metrics.execution_time:.1f}s",
            },
            "quality_gates": report.quality_gates,
            "categories": [asdict(cat) for cat in report.categories],
            "recommendations": report.recommendations,
            "status": (
                "PASSED" if report.quality_gates["all_tests_passing"] else "FAILED"
            ),
        }

    def _fallback_pdf_generation(self, report: TestReport) -> Optional[Path]:
        """Fallback PDF generation using system tools."""
        html_path = self.output_dir / "comprehensive_test_report.html"
        pdf_path = self.output_dir / "test_report_fallback.pdf"

        # Try WeasyPrint first
        try:
            import weasyprint

            logger.info("Generating PDF using WeasyPrint...")
            weasyprint.HTML(filename=str(html_path)).write_pdf(str(pdf_path))
            logger.info(f"WeasyPrint PDF generated: {pdf_path}")
            return pdf_path
        except ImportError:
            logger.warning("WeasyPrint not available")
        except Exception as e:
            logger.warning(f"WeasyPrint failed: {e}")

        # Try wkhtmltopdf as secondary fallback
        try:
            cmd = ["wkhtmltopdf", "--page-size", "A4", str(html_path), str(pdf_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"wkhtmltopdf PDF generated: {pdf_path}")
                return pdf_path
            else:
                logger.error(f"wkhtmltopdf failed: {result.stderr}")

        except FileNotFoundError:
            logger.warning("wkhtmltopdf not found")
        except Exception as e:
            logger.error(f"wkhtmltopdf failed: {e}")

        logger.warning("PDF generation skipped - no suitable PDF generator available")
        return None

    def _generate_executive_summary(self, report: TestReport) -> Optional[Path]:
        """Generate executive summary PDF."""
        logger.info("📋 Generating executive summary...")

        try:
            summary_data = {
                "project_name": report.project_name,
                "timestamp": report.timestamp,
                "status": (
                    "PASSED" if report.quality_gates["all_tests_passing"] else "FAILED"
                ),
                "key_metrics": {
                    "Total Tests": report.metrics.total_tests,
                    "Pass Rate": f"{report.metrics.pass_rate:.1f}%",
                    "Coverage": f"{report.metrics.coverage_percentage:.1f}%",
                    "Execution Time": f"{report.metrics.execution_time:.1f}s",
                },
                "quality_summary": {
                    "gates_passed": sum(
                        1 for passed in report.quality_gates.values() if passed
                    ),
                    "total_gates": len(report.quality_gates),
                    "critical_issues": report.metrics.failed_tests
                    + report.metrics.error_tests,
                },
                "top_recommendations": report.recommendations[:3],
                "next_steps": (
                    [
                        "Review failed tests and fix issues",
                        "Increase test coverage if below threshold",
                        "Optimize slow tests for better performance",
                    ]
                    if report.metrics.failed_tests > 0
                    else [
                        "Maintain high test quality",
                        "Consider adding more integration tests",
                        "Monitor performance benchmarks",
                    ]
                ),
            }

            # Generate executive summary PDF
            response = requests.post(
                f"{self.pdf_service_url}/api/pdf/generate-sync",
                json={
                    "templateId": "executive-summary",
                    "data": summary_data,
                    "returnBuffer": False,
                    "format": "A4",
                },
                timeout=60,
            )

            if response.status_code == 200:
                summary_path = self.output_dir / "executive_summary.pdf"

                if response.headers.get("content-type") == "application/pdf":
                    with open(summary_path, "wb") as f:
                        f.write(response.content)

                    logger.info(f"Executive summary saved to: {summary_path}")
                    return summary_path

        except Exception as e:
            logger.warning(f"Executive summary generation failed: {e}")

        return None


def main():
    """Main entry point for test report generation."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate comprehensive test reports")
    parser.add_argument("--project-name", default="ICE Pipeline", help="Project name")
    parser.add_argument(
        "--pdf-service", default="http://localhost:4000", help="PDF service URL"
    )
    parser.add_argument(
        "--no-run", action="store_true", help="Don't run tests, use existing results"
    )

    args = parser.parse_args()

    generator = TestReportGenerator(
        project_name=args.project_name, pdf_service_url=args.pdf_service
    )

    results = generator.generate_report(run_tests=not args.no_run)

    print("\n🎉 Test Report Generation Complete!")
    print(f"📊 HTML Report: {results['html_report']}")
    if results["pdf_report"]:
        print(f"📄 PDF Report: {results['pdf_report']}")
    if results["executive_summary"]:
        print(f"📋 Executive Summary: {results['executive_summary']}")
    print(f"💾 Raw Data: {results['json_data']}")


if __name__ == "__main__":
    main()
