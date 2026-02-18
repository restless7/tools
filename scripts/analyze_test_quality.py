#!/usr/bin/env python3
"""
Test Quality Analyzer
====================

Enterprise-grade test quality analysis system for comprehensive quality metrics.
This script analyzes test results across multiple dimensions to provide insights
for continuous improvement and enterprise-level quality assurance.

Features:
- Multi-dimensional quality analysis
- Trend detection and regression analysis
- Risk assessment and early warning systems
- Scalable architecture for enterprise use
- Integration with CI/CD pipelines
"""

import argparse
import json
import statistics
import defusedxml.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class QualityThreshold:
    """Quality threshold definition for enterprise standards."""

    name: str
    metric: str
    threshold: float
    operator: str  # 'gte', 'lte', 'eq'
    severity: str  # 'critical', 'high', 'medium', 'low'
    description: str


@dataclass
class QualityMetric:
    """Quality metric with historical data."""

    name: str
    current_value: float
    previous_value: Optional[float]
    trend: str  # 'improving', 'degrading', 'stable'
    change_percentage: float
    status: str  # 'pass', 'warning', 'fail'
    category: str


class TestQualityAnalyzer:
    """
    Enterprise test quality analyzer with modular architecture.
    """

    def __init__(self, config_file: Optional[Path] = None):
        self.config = self.load_config(config_file)
        self.quality_thresholds = self.load_thresholds()
        self.metrics = {}
        self.analysis_results = {}
        self.historical_data = {}

    def load_config(self, config_file: Optional[Path]) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        default_config = {
            "analysis_depth": "comprehensive",
            "trend_analysis_days": 30,
            "regression_threshold": 5.0,
            "enable_predictions": True,
            "quality_categories": [
                "test_execution",
                "code_coverage",
                "test_reliability",
                "performance",
                "security",
            ],
        }

        if config_file and config_file.exists():
            try:
                with open(config_file, "r") as f:
                    user_config = yaml.safe_load(f)
                    default_config.update(user_config)
            except Exception as e:
                print(f"Warning: Could not load config file {config_file}: {e}")

        return default_config

    def load_thresholds(self) -> List[QualityThreshold]:
        """Load quality thresholds for enterprise standards."""
        return [
            # Test Execution Quality
            QualityThreshold(
                name="Test Success Rate",
                metric="success_rate",
                threshold=95.0,
                operator="gte",
                severity="critical",
                description="Percentage of tests that pass successfully",
            ),
            QualityThreshold(
                name="Test Reliability",
                metric="flaky_test_percentage",
                threshold=2.0,
                operator="lte",
                severity="high",
                description="Percentage of tests that are inconsistent",
            ),
            QualityThreshold(
                name="Test Execution Time",
                metric="average_execution_time",
                threshold=300.0,  # 5 minutes
                operator="lte",
                severity="medium",
                description="Average test execution time in seconds",
            ),
            # Code Coverage Quality
            QualityThreshold(
                name="Line Coverage",
                metric="line_coverage",
                threshold=80.0,
                operator="gte",
                severity="high",
                description="Percentage of code lines covered by tests",
            ),
            QualityThreshold(
                name="Branch Coverage",
                metric="branch_coverage",
                threshold=75.0,
                operator="gte",
                severity="high",
                description="Percentage of code branches covered by tests",
            ),
            QualityThreshold(
                name="Function Coverage",
                metric="function_coverage",
                threshold=85.0,
                operator="gte",
                severity="medium",
                description="Percentage of functions covered by tests",
            ),
            # Performance Quality
            QualityThreshold(
                name="Performance Regression",
                metric="performance_regression",
                threshold=10.0,
                operator="lte",
                severity="high",
                description="Percentage performance degradation from baseline",
            ),
            QualityThreshold(
                name="Memory Usage",
                metric="peak_memory_usage",
                threshold=1024.0,  # 1GB
                operator="lte",
                severity="medium",
                description="Peak memory usage during test execution (MB)",
            ),
            # Security Quality
            QualityThreshold(
                name="Critical Security Issues",
                metric="critical_security_issues",
                threshold=0,
                operator="lte",
                severity="critical",
                description="Number of critical security vulnerabilities",
            ),
            QualityThreshold(
                name="High Security Issues",
                metric="high_security_issues",
                threshold=0,
                operator="lte",
                severity="high",
                description="Number of high-severity security vulnerabilities",
            ),
        ]

    def analyze_test_execution_quality(self, artifacts_dir: Path) -> Dict[str, Any]:
        """
        Analyze test execution quality metrics.

        Args:
            artifacts_dir: Directory containing test artifacts

        Returns:
            Test execution quality analysis
        """
        analysis = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "flaky_tests": 0,
            "success_rate": 0.0,
            "failure_rate": 0.0,
            "flaky_test_percentage": 0.0,
            "average_execution_time": 0.0,
            "test_suites": [],
            "problematic_tests": [],
            "execution_trends": {},
        }

        # Parse JUnit XML files
        junit_files = list(artifacts_dir.glob("**/*.xml"))
        total_execution_time = 0.0
        test_results = {}

        for xml_file in junit_files:
            if "junit" in xml_file.name.lower() or "test" in xml_file.name.lower():
                suite_data = self.parse_junit_xml(xml_file)
                if suite_data:
                    analysis["test_suites"].append(suite_data)
                    analysis["total_tests"] += suite_data.get("tests", 0)
                    analysis["failed_tests"] += suite_data.get(
                        "failures", 0
                    ) + suite_data.get("errors", 0)
                    analysis["skipped_tests"] += suite_data.get("skipped", 0)
                    total_execution_time += suite_data.get("time", 0.0)

                    # Track individual test results for flaky test detection
                    for test_case in suite_data.get("test_cases", []):
                        test_key = f"{test_case.get('classname', '')}.{test_case.get('name', '')}"
                        if test_key not in test_results:
                            test_results[test_key] = []
                        test_results[test_key].append(
                            test_case.get("status", "unknown")
                        )

        analysis["passed_tests"] = (
            analysis["total_tests"]
            - analysis["failed_tests"]
            - analysis["skipped_tests"]
        )

        # Calculate rates and averages
        if analysis["total_tests"] > 0:
            analysis["success_rate"] = (
                analysis["passed_tests"] / analysis["total_tests"]
            ) * 100
            analysis["failure_rate"] = (
                analysis["failed_tests"] / analysis["total_tests"]
            ) * 100
            analysis["average_execution_time"] = (
                total_execution_time / len(analysis["test_suites"])
                if analysis["test_suites"]
                else 0.0
            )

        # Detect flaky tests (tests with inconsistent results)
        flaky_tests = []
        for test_name, results in test_results.items():
            if len(set(results)) > 1:  # Test has different outcomes
                flaky_tests.append(
                    {
                        "test_name": test_name,
                        "results": results,
                        "failure_rate": results.count("failed") / len(results) * 100,
                    }
                )
                analysis["flaky_tests"] += 1

        analysis["flaky_test_percentage"] = (
            (analysis["flaky_tests"] / analysis["total_tests"] * 100)
            if analysis["total_tests"] > 0
            else 0.0
        )
        analysis["problematic_tests"] = sorted(
            flaky_tests, key=lambda x: x["failure_rate"], reverse=True
        )[:10]

        return analysis

    def analyze_coverage_quality(self, artifacts_dir: Path) -> Dict[str, Any]:
        """
        Analyze code coverage quality metrics.

        Args:
            artifacts_dir: Directory containing coverage reports

        Returns:
            Coverage quality analysis
        """
        analysis = {
            "line_coverage": 0.0,
            "branch_coverage": 0.0,
            "function_coverage": 0.0,
            "complexity_coverage": 0.0,
            "uncovered_lines": 0,
            "uncovered_branches": 0,
            "critical_paths_coverage": 0.0,
            "coverage_trends": {},
            "coverage_by_module": [],
            "low_coverage_files": [],
        }

        # Parse coverage XML files
        coverage_files = list(artifacts_dir.glob("**/coverage*.xml"))

        total_line_rate = 0.0
        total_branch_rate = 0.0
        coverage_count = 0

        for cov_file in coverage_files:
            cov_data = self.parse_coverage_xml(cov_file)
            if cov_data:
                analysis["line_coverage"] += cov_data.get("line_rate", 0.0)
                analysis["branch_coverage"] += cov_data.get("branch_rate", 0.0)
                analysis["uncovered_lines"] += cov_data.get(
                    "lines_valid", 0
                ) - cov_data.get("lines_covered", 0)
                analysis["uncovered_branches"] += cov_data.get(
                    "branches_valid", 0
                ) - cov_data.get("branches_covered", 0)
                coverage_count += 1

                # Analyze coverage by module/package
                for package in cov_data.get("packages", []):
                    module_analysis = {
                        "name": package["name"],
                        "line_coverage": package["line_rate"],
                        "branch_coverage": package["branch_rate"],
                        "complexity": package.get("complexity", 0),
                        "risk_level": self.calculate_risk_level(
                            package["line_rate"], package.get("complexity", 0)
                        ),
                    }
                    analysis["coverage_by_module"].append(module_analysis)

                    # Identify low coverage files
                    if package["line_rate"] < 60.0:
                        analysis["low_coverage_files"].append(
                            {
                                "file": package["name"],
                                "coverage": package["line_rate"],
                                "priority": (
                                    "high" if package["line_rate"] < 40.0 else "medium"
                                ),
                            }
                        )

        # Calculate averages
        if coverage_count > 0:
            analysis["line_coverage"] /= coverage_count
            analysis["branch_coverage"] /= coverage_count

        # Sort modules by risk level
        analysis["coverage_by_module"].sort(key=lambda x: x["risk_level"], reverse=True)
        analysis["low_coverage_files"].sort(key=lambda x: x["coverage"])

        return analysis

    def analyze_performance_quality(self, artifacts_dir: Path) -> Dict[str, Any]:
        """
        Analyze performance quality metrics.

        Args:
            artifacts_dir: Directory containing performance test results

        Returns:
            Performance quality analysis
        """
        analysis = {
            "average_response_time": 0.0,
            "peak_memory_usage": 0.0,
            "cpu_utilization": 0.0,
            "performance_regression": 0.0,
            "slow_tests": [],
            "memory_intensive_tests": [],
            "performance_trends": {},
            "bottlenecks": [],
        }

        # Parse performance test results
        performance_files = list(artifacts_dir.glob("**/performance*.xml"))

        execution_times = []
        memory_usage = []

        for perf_file in performance_files:
            suite_data = self.parse_junit_xml(perf_file)
            if suite_data:
                for test_case in suite_data.get("test_cases", []):
                    execution_time = test_case.get("time", 0.0)
                    execution_times.append(execution_time)

                    # Identify slow tests
                    if execution_time > 30.0:  # Tests taking more than 30 seconds
                        analysis["slow_tests"].append(
                            {
                                "test_name": f"{test_case.get('classname', '')}.{test_case.get('name', '')}",
                                "execution_time": execution_time,
                                "category": "slow",
                            }
                        )

        # Calculate performance metrics
        if execution_times:
            analysis["average_response_time"] = statistics.mean(execution_times)
            analysis["performance_trends"]["p50"] = statistics.median(execution_times)
            analysis["performance_trends"]["p95"] = (
                statistics.quantiles(execution_times, n=20)[18]
                if len(execution_times) > 20
                else max(execution_times)
            )
            analysis["performance_trends"]["p99"] = (
                statistics.quantiles(execution_times, n=100)[98]
                if len(execution_times) > 100
                else max(execution_times)
            )

        # Sort slow tests by execution time
        analysis["slow_tests"].sort(key=lambda x: x["execution_time"], reverse=True)
        analysis["slow_tests"] = analysis["slow_tests"][:10]  # Top 10 slowest

        return analysis

    def analyze_security_quality(self, artifacts_dir: Path) -> Dict[str, Any]:
        """
        Analyze security quality metrics from security scan results.

        Args:
            artifacts_dir: Directory containing security reports

        Returns:
            Security quality analysis
        """
        analysis = {
            "critical_security_issues": 0,
            "high_security_issues": 0,
            "medium_security_issues": 0,
            "low_security_issues": 0,
            "total_security_issues": 0,
            "security_score": 100.0,
            "vulnerability_categories": {},
            "affected_packages": [],
            "security_trends": {},
            "compliance_status": "compliant",
        }

        # Parse Bandit reports
        bandit_files = list(artifacts_dir.glob("**/bandit-report.json"))
        for bandit_file in bandit_files:
            try:
                with open(bandit_file, "r") as f:
                    bandit_data = json.load(f)

                for result in bandit_data.get("results", []):
                    severity = result.get("issue_severity", "UNKNOWN").lower()

                    if severity == "high":
                        analysis["high_security_issues"] += 1
                    elif severity == "medium":
                        analysis["medium_security_issues"] += 1
                    elif severity == "low":
                        analysis["low_security_issues"] += 1

                    analysis["total_security_issues"] += 1

                    # Categorize vulnerabilities
                    test_name = result.get("test_name", "unknown")
                    if test_name not in analysis["vulnerability_categories"]:
                        analysis["vulnerability_categories"][test_name] = 0
                    analysis["vulnerability_categories"][test_name] += 1

            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Warning: Could not parse Bandit report {bandit_file}: {e}")

        # Parse Safety reports
        safety_files = list(artifacts_dir.glob("**/safety-report.json"))
        for safety_file in safety_files:
            try:
                with open(safety_file, "r") as f:
                    safety_data = json.load(f)

                for vuln in safety_data:
                    analysis[
                        "critical_security_issues"
                    ] += 1  # Treat dependency vulnerabilities as critical
                    analysis["total_security_issues"] += 1

                    package_name = vuln.get("package", "unknown")
                    if package_name not in [
                        pkg["name"] for pkg in analysis["affected_packages"]
                    ]:
                        analysis["affected_packages"].append(
                            {
                                "name": package_name,
                                "installed_version": vuln.get("installed_version", ""),
                                "vulnerability_count": 1,
                                "cves": [vuln.get("cve", "")],
                            }
                        )
                    else:
                        # Update existing package
                        for pkg in analysis["affected_packages"]:
                            if pkg["name"] == package_name:
                                pkg["vulnerability_count"] += 1
                                if vuln.get("cve"):
                                    pkg["cves"].append(vuln.get("cve"))
                                break

            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Warning: Could not parse Safety report {safety_file}: {e}")

        # Calculate security score
        if analysis["total_security_issues"] == 0:
            analysis["security_score"] = 100.0
        else:
            # Weighted scoring: critical issues have higher impact
            weighted_issues = (
                analysis["critical_security_issues"] * 10
                + analysis["high_security_issues"] * 5
                + analysis["medium_security_issues"] * 2
                + analysis["low_security_issues"] * 1
            )
            analysis["security_score"] = max(0, 100 - weighted_issues)

        # Determine compliance status
        if (
            analysis["critical_security_issues"] > 0
            or analysis["high_security_issues"] > 5
        ):
            analysis["compliance_status"] = "non-compliant"
        elif analysis["medium_security_issues"] > 10:
            analysis["compliance_status"] = "at-risk"

        return analysis

    def calculate_risk_level(self, coverage: float, complexity: float) -> float:
        """
        Calculate risk level based on coverage and complexity.

        Args:
            coverage: Code coverage percentage
            complexity: Code complexity score

        Returns:
            Risk level (0-100, higher is more risky)
        """
        # Risk increases with lower coverage and higher complexity
        coverage_risk = max(0, 100 - coverage) * 0.7
        complexity_risk = min(complexity * 10, 100) * 0.3
        return coverage_risk + complexity_risk

    def generate_quality_metrics(self, artifacts_dir: Path) -> Dict[str, QualityMetric]:
        """
        Generate comprehensive quality metrics for enterprise analysis.

        Args:
            artifacts_dir: Directory containing test artifacts

        Returns:
            Dictionary of quality metrics
        """
        metrics = {}

        # Analyze different quality dimensions
        execution_analysis = self.analyze_test_execution_quality(artifacts_dir)
        coverage_analysis = self.analyze_coverage_quality(artifacts_dir)
        performance_analysis = self.analyze_performance_quality(artifacts_dir)
        security_analysis = self.analyze_security_quality(artifacts_dir)

        # Create quality metrics
        metric_definitions = [
            ("success_rate", execution_analysis["success_rate"], "test_execution"),
            (
                "flaky_test_percentage",
                execution_analysis["flaky_test_percentage"],
                "test_execution",
            ),
            (
                "average_execution_time",
                execution_analysis["average_execution_time"],
                "test_execution",
            ),
            ("line_coverage", coverage_analysis["line_coverage"], "code_coverage"),
            ("branch_coverage", coverage_analysis["branch_coverage"], "code_coverage"),
            (
                "average_response_time",
                performance_analysis["average_response_time"],
                "performance",
            ),
            (
                "peak_memory_usage",
                performance_analysis["peak_memory_usage"],
                "performance",
            ),
            (
                "critical_security_issues",
                security_analysis["critical_security_issues"],
                "security",
            ),
            (
                "high_security_issues",
                security_analysis["high_security_issues"],
                "security",
            ),
            ("security_score", security_analysis["security_score"], "security"),
        ]

        for metric_name, current_value, category in metric_definitions:
            # Load historical data if available
            previous_value = self.get_historical_value(metric_name)

            # Calculate trend and change percentage
            if previous_value is not None:
                change_percentage = (
                    ((current_value - previous_value) / previous_value * 100)
                    if previous_value != 0
                    else 0
                )
                if abs(change_percentage) <= self.config["regression_threshold"]:
                    trend = "stable"
                elif change_percentage > 0:
                    # For metrics where higher is better (coverage, success rate, security score)
                    if metric_name in [
                        "success_rate",
                        "line_coverage",
                        "branch_coverage",
                        "security_score",
                    ]:
                        trend = "improving"
                    else:
                        trend = "degrading"
                else:
                    # For metrics where lower is better (execution time, security issues)
                    if metric_name in [
                        "success_rate",
                        "line_coverage",
                        "branch_coverage",
                        "security_score",
                    ]:
                        trend = "degrading"
                    else:
                        trend = "improving"
            else:
                change_percentage = 0.0
                trend = "stable"

            # Determine status based on thresholds
            status = "pass"
            for threshold in self.quality_thresholds:
                if threshold.metric == metric_name:
                    if (
                        threshold.operator == "gte"
                        and current_value < threshold.threshold
                    ):
                        status = "fail"
                    elif (
                        threshold.operator == "lte"
                        and current_value > threshold.threshold
                    ):
                        status = "fail"
                    elif (
                        threshold.operator == "eq"
                        and current_value != threshold.threshold
                    ):
                        status = "fail"
                    break

            metrics[metric_name] = QualityMetric(
                name=metric_name,
                current_value=current_value,
                previous_value=previous_value,
                trend=trend,
                change_percentage=change_percentage,
                status=status,
                category=category,
            )

        return metrics

    def get_historical_value(self, metric_name: str) -> Optional[float]:
        """
        Get historical value for a metric (placeholder for actual implementation).

        Args:
            metric_name: Name of the metric

        Returns:
            Historical value if available
        """
        # This would typically load from a database or file system
        # For now, return None to indicate no historical data
        return None

    def generate_quality_report(self, artifacts_dir: Path, output_file: Path) -> None:
        """
        Generate comprehensive quality analysis report.

        Args:
            artifacts_dir: Directory containing test artifacts
            output_file: Path to output JSON file
        """
        # Generate metrics
        quality_metrics = self.generate_quality_metrics(artifacts_dir)

        # Prepare report data
        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "analysis_version": "1.0.0",
                "config": self.config,
            },
            "quality_summary": {
                "overall_score": self.calculate_overall_quality_score(quality_metrics),
                "quality_gates": self.check_quality_gates(quality_metrics),
                "risk_assessment": self.assess_quality_risks(quality_metrics),
            },
            "metrics": {
                name: {
                    "current_value": metric.current_value,
                    "previous_value": metric.previous_value,
                    "trend": metric.trend,
                    "change_percentage": metric.change_percentage,
                    "status": metric.status,
                    "category": metric.category,
                }
                for name, metric in quality_metrics.items()
            },
            "detailed_analysis": {
                "test_execution": self.analyze_test_execution_quality(artifacts_dir),
                "code_coverage": self.analyze_coverage_quality(artifacts_dir),
                "performance": self.analyze_performance_quality(artifacts_dir),
                "security": self.analyze_security_quality(artifacts_dir),
            },
            "recommendations": self.generate_recommendations(quality_metrics),
            "thresholds": {
                t.name: {
                    "metric": t.metric,
                    "threshold": t.threshold,
                    "operator": t.operator,
                    "severity": t.severity,
                    "description": t.description,
                }
                for t in self.quality_thresholds
            },
        }

        # Save report
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            print(f"✅ Quality analysis report generated: {output_file}")

        except Exception as e:
            print(f"❌ Error generating quality report: {e}")

    def calculate_overall_quality_score(
        self, metrics: Dict[str, QualityMetric]
    ) -> float:
        """
        Calculate overall quality score based on all metrics.

        Args:
            metrics: Dictionary of quality metrics

        Returns:
            Overall quality score (0-100)
        """
        category_weights = {
            "test_execution": 0.30,
            "code_coverage": 0.25,
            "performance": 0.20,
            "security": 0.25,
        }

        category_scores = {}

        for category in category_weights.keys():
            category_metrics = [m for m in metrics.values() if m.category == category]
            if category_metrics:
                # Calculate weighted score for each category
                if category == "test_execution":
                    # Higher success rate and lower flaky tests = better score
                    success_rate = next(
                        (
                            m.current_value
                            for m in category_metrics
                            if "success_rate" in m.name
                        ),
                        95.0,
                    )
                    flaky_percentage = next(
                        (
                            m.current_value
                            for m in category_metrics
                            if "flaky" in m.name
                        ),
                        0.0,
                    )
                    category_scores[category] = max(0, success_rate - flaky_percentage)
                elif category == "code_coverage":
                    # Average of line and branch coverage
                    coverages = [
                        m.current_value
                        for m in category_metrics
                        if "coverage" in m.name
                    ]
                    category_scores[category] = (
                        statistics.mean(coverages) if coverages else 0.0
                    )
                elif category == "performance":
                    # Based on execution time (inverted - lower is better)
                    avg_time = next(
                        (
                            m.current_value
                            for m in category_metrics
                            if "response_time" in m.name
                        ),
                        60.0,
                    )
                    category_scores[category] = max(
                        0, 100 - (avg_time / 10)
                    )  # Scale appropriately
                elif category == "security":
                    # Use security score directly
                    security_score = next(
                        (
                            m.current_value
                            for m in category_metrics
                            if "security_score" in m.name
                        ),
                        100.0,
                    )
                    category_scores[category] = security_score

        # Calculate weighted overall score
        overall_score = sum(
            category_scores.get(category, 0.0) * weight
            for category, weight in category_weights.items()
        )

        return min(100.0, max(0.0, overall_score))

    def check_quality_gates(self, metrics: Dict[str, QualityMetric]) -> Dict[str, Any]:
        """
        Check quality gates against enterprise thresholds.

        Args:
            metrics: Dictionary of quality metrics

        Returns:
            Quality gates status
        """
        gates = {
            "overall_status": "PASS",
            "failed_gates": [],
            "warning_gates": [],
            "passed_gates": [],
        }

        for threshold in self.quality_thresholds:
            metric = metrics.get(threshold.metric)
            if metric:
                gate_status = {
                    "name": threshold.name,
                    "metric": threshold.metric,
                    "threshold": threshold.threshold,
                    "actual": metric.current_value,
                    "status": metric.status,
                    "severity": threshold.severity,
                }

                if metric.status == "fail":
                    if threshold.severity in ["critical", "high"]:
                        gates["failed_gates"].append(gate_status)
                    else:
                        gates["warning_gates"].append(gate_status)
                else:
                    gates["passed_gates"].append(gate_status)

        # Set overall status
        if gates["failed_gates"]:
            gates["overall_status"] = "FAIL"
        elif gates["warning_gates"]:
            gates["overall_status"] = "WARNING"

        return gates

    def assess_quality_risks(self, metrics: Dict[str, QualityMetric]) -> Dict[str, Any]:
        """
        Assess quality risks based on trends and thresholds.

        Args:
            metrics: Dictionary of quality metrics

        Returns:
            Risk assessment
        """
        risks = {
            "overall_risk": "low",
            "risk_factors": [],
            "trending_issues": [],
            "immediate_actions": [],
        }

        high_risk_count = 0

        for metric in metrics.values():
            # Check for degrading trends
            if (
                metric.trend == "degrading"
                and abs(metric.change_percentage) > self.config["regression_threshold"]
            ):
                risks["trending_issues"].append(
                    {
                        "metric": metric.name,
                        "trend": metric.trend,
                        "change_percentage": metric.change_percentage,
                        "category": metric.category,
                    }
                )
                high_risk_count += 1

            # Check for failing metrics
            if metric.status == "fail":
                risks["risk_factors"].append(
                    {
                        "metric": metric.name,
                        "current_value": metric.current_value,
                        "category": metric.category,
                        "severity": (
                            "high" if metric.category == "security" else "medium"
                        ),
                    }
                )
                high_risk_count += 1

        # Determine overall risk level
        if high_risk_count >= 3:
            risks["overall_risk"] = "high"
        elif high_risk_count >= 1:
            risks["overall_risk"] = "medium"

        # Generate immediate actions
        if risks["risk_factors"]:
            risks["immediate_actions"].extend(
                [
                    "Review and address failing quality gates",
                    "Investigate root causes of metric degradation",
                    "Implement corrective measures for high-priority issues",
                ]
            )

        return risks

    def generate_recommendations(
        self, metrics: Dict[str, QualityMetric]
    ) -> List[Dict[str, str]]:
        """
        Generate actionable recommendations based on quality analysis.

        Args:
            metrics: Dictionary of quality metrics

        Returns:
            List of recommendations
        """
        recommendations = []

        # Test execution recommendations
        success_rate = metrics.get("success_rate")
        if success_rate and success_rate.current_value < 95.0:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "category": "Test Execution",
                    "title": "Improve Test Reliability",
                    "description": f"Test success rate is {success_rate.current_value:.1f}%, below the 95% threshold",
                    "action": "Identify and fix flaky tests, improve test environment stability",
                }
            )

        # Coverage recommendations
        line_coverage = metrics.get("line_coverage")
        if line_coverage and line_coverage.current_value < 80.0:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": "Code Coverage",
                    "title": "Increase Test Coverage",
                    "description": f"Line coverage is {line_coverage.current_value:.1f}%, below the 80% threshold",
                    "action": "Add unit tests for uncovered code paths, focus on critical business logic",
                }
            )

        # Performance recommendations
        response_time = metrics.get("average_response_time")
        if response_time and response_time.current_value > 60.0:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": "Performance",
                    "title": "Optimize Test Performance",
                    "description": f"Average test execution time is {response_time.current_value:.1f}s, which may impact CI/CD efficiency",
                    "action": "Optimize slow tests, parallelize test execution, review test data setup",
                }
            )

        # Security recommendations
        security_issues = metrics.get("critical_security_issues")
        if security_issues and security_issues.current_value > 0:
            recommendations.append(
                {
                    "priority": "CRITICAL",
                    "category": "Security",
                    "title": "Address Critical Security Issues",
                    "description": f"Found {int(security_issues.current_value)} critical security issues",
                    "action": "Immediately review and fix critical security vulnerabilities",
                }
            )

        return recommendations

    def parse_junit_xml(self, xml_path: Path) -> Dict[str, Any]:
        """Parse JUnit XML files (reused from reporter)."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            test_suite = {
                "name": root.get("name", "Unknown"),
                "tests": int(root.get("tests", 0)),
                "failures": int(root.get("failures", 0)),
                "errors": int(root.get("errors", 0)),
                "skipped": int(root.get("skipped", 0)),
                "time": float(root.get("time", 0.0)),
                "test_cases": [],
            }

            for testcase in root.findall(".//testcase"):
                case_data = {
                    "classname": testcase.get("classname", ""),
                    "name": testcase.get("name", ""),
                    "time": float(testcase.get("time", 0.0)),
                    "status": "passed",
                }

                if testcase.find("failure") is not None:
                    case_data["status"] = "failed"
                elif testcase.find("error") is not None:
                    case_data["status"] = "error"
                elif testcase.find("skipped") is not None:
                    case_data["status"] = "skipped"

                test_suite["test_cases"].append(case_data)

            return test_suite

        except Exception as e:
            print(f"Error parsing XML file {xml_path}: {e}")
            return {}

    def parse_coverage_xml(self, xml_path: Path) -> Dict[str, Any]:
        """Parse coverage XML files (reused from reporter)."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            coverage_data = {
                "line_rate": float(root.get("line-rate", 0.0)) * 100,
                "branch_rate": float(root.get("branch-rate", 0.0)) * 100,
                "lines_covered": int(root.get("lines-covered", 0)),
                "lines_valid": int(root.get("lines-valid", 0)),
                "branches_covered": int(root.get("branches-covered", 0)),
                "branches_valid": int(root.get("branches-valid", 0)),
                "packages": [],
            }

            for package in root.findall(".//package"):
                package_data = {
                    "name": package.get("name", ""),
                    "line_rate": float(package.get("line-rate", 0.0)) * 100,
                    "branch_rate": float(package.get("branch-rate", 0.0)) * 100,
                    "complexity": float(package.get("complexity", 0.0)),
                }
                coverage_data["packages"].append(package_data)

            return coverage_data

        except Exception as e:
            print(f"Error parsing coverage XML {xml_path}: {e}")
            return {}


def main():
    """Main entry point for test quality analyzer."""
    parser = argparse.ArgumentParser(description="Enterprise Test Quality Analyzer")
    parser.add_argument(
        "--artifacts-dir", required=True, help="Directory containing test artifacts"
    )
    parser.add_argument(
        "--threshold-file", help="YAML file with custom quality thresholds"
    )
    parser.add_argument(
        "--output", required=True, help="Output JSON file for quality analysis"
    )
    parser.add_argument("--config", help="Configuration file for analysis parameters")

    args = parser.parse_args()

    # Initialize analyzer
    config_file = Path(args.config) if args.config else None
    analyzer = TestQualityAnalyzer(config_file)

    # Generate quality analysis
    print("🔍 Analyzing test quality...")
    analyzer.generate_quality_report(Path(args.artifacts_dir), Path(args.output))

    print("✅ Quality analysis complete!")


if __name__ == "__main__":
    main()
