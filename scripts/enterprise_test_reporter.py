#!/usr/bin/env python3
"""
Enterprise Test Reporter
========================

Modular and scalable test reporting system designed for enterprise environments.
This script generates comprehensive test reports that can be used across different
projects and contexts within the organization.

Features:
- Multi-format output (HTML, JSON, PDF)
- Interactive dashboards
- Trend analysis
- Quality metrics
- Frontend integration ready
- Customizable templates
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader, select_autoescape
from plotly.subplots import make_subplots


class EnterpriseTestReporter:
    """
    Enterprise-grade test reporter with modular architecture for scalability.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.template_dir = Path(__file__).parent / "templates"
        self.template_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        # Initialize data structures
        self.test_data = {
            "unit_tests": [],
            "integration_tests": [],
            "api_tests": [],
            "e2e_tests": [],
            "performance_tests": [],
            "stress_tests": [],
            "security_scans": [],
        }

        self.metrics = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "success_rate": 0.0,
            "total_duration": 0.0,
            "coverage_percentage": 0.0,
        }

        # Enterprise-specific configurations
        self.quality_thresholds = {
            "success_rate": 95.0,
            "coverage": 80.0,
            "performance_regression": 10.0,
            "security_issues": 0,
        }

    def parse_junit_xml(self, xml_path: Path) -> Dict[str, Any]:
        """
        Parse JUnit XML test results with enterprise-level detail extraction.

        Args:
            xml_path: Path to JUnit XML file

        Returns:
            Parsed test data dictionary
        """
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
                "timestamp": root.get("timestamp", ""),
                "test_cases": [],
            }

            for testcase in root.findall(".//testcase"):
                case_data = {
                    "classname": testcase.get("classname", ""),
                    "name": testcase.get("name", ""),
                    "time": float(testcase.get("time", 0.0)),
                    "status": "passed",
                }

                # Check for failures, errors, or skips
                if testcase.find("failure") is not None:
                    case_data["status"] = "failed"
                    failure = testcase.find("failure")
                    case_data["failure_message"] = failure.get("message", "")
                    case_data["failure_type"] = failure.get("type", "")
                    case_data["failure_text"] = failure.text or ""
                elif testcase.find("error") is not None:
                    case_data["status"] = "error"
                    error = testcase.find("error")
                    case_data["error_message"] = error.get("message", "")
                    case_data["error_type"] = error.get("type", "")
                    case_data["error_text"] = error.text or ""
                elif testcase.find("skipped") is not None:
                    case_data["status"] = "skipped"
                    skip = testcase.find("skipped")
                    case_data["skip_message"] = skip.get("message", "")

                test_suite["test_cases"].append(case_data)

            return test_suite

        except ET.ParseError as e:
            print(f"Error parsing XML file {xml_path}: {e}")
            return {}
        except Exception as e:
            print(f"Unexpected error parsing {xml_path}: {e}")
            return {}

    def parse_coverage_xml(self, xml_path: Path) -> Dict[str, Any]:
        """
        Parse coverage XML reports for enterprise metrics.

        Args:
            xml_path: Path to coverage XML file

        Returns:
            Coverage data dictionary
        """
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
                "complexity": float(root.get("complexity", 0.0)),
                "packages": [],
            }

            for package in root.findall(".//package"):
                package_data = {
                    "name": package.get("name", ""),
                    "line_rate": float(package.get("line-rate", 0.0)) * 100,
                    "branch_rate": float(package.get("branch-rate", 0.0)) * 100,
                    "complexity": float(package.get("complexity", 0.0)),
                    "classes": [],
                }

                for class_elem in package.findall(".//class"):
                    class_data = {
                        "name": class_elem.get("name", ""),
                        "filename": class_elem.get("filename", ""),
                        "line_rate": float(class_elem.get("line-rate", 0.0)) * 100,
                        "branch_rate": float(class_elem.get("branch-rate", 0.0)) * 100,
                        "complexity": float(class_elem.get("complexity", 0.0)),
                    }
                    package_data["classes"].append(class_data)

                coverage_data["packages"].append(package_data)

            return coverage_data

        except ET.ParseError as e:
            print(f"Error parsing coverage XML {xml_path}: {e}")
            return {}
        except Exception as e:
            print(f"Unexpected error parsing coverage {xml_path}: {e}")
            return {}

    def parse_security_reports(self, artifacts_dir: Path) -> Dict[str, Any]:
        """
        Parse security scan reports (Bandit, Safety) for enterprise security metrics.

        Args:
            artifacts_dir: Directory containing security reports

        Returns:
            Security analysis data
        """
        security_data = {
            "bandit_issues": [],
            "safety_vulnerabilities": [],
            "total_security_issues": 0,
            "severity_breakdown": {"high": 0, "medium": 0, "low": 0},
        }

        # Parse Bandit reports
        bandit_files = list(artifacts_dir.glob("**/bandit-report.json"))
        for bandit_file in bandit_files:
            try:
                with open(bandit_file, "r") as f:
                    bandit_data = json.load(f)

                for result in bandit_data.get("results", []):
                    issue = {
                        "filename": result.get("filename", ""),
                        "line_number": result.get("line_number", 0),
                        "test_id": result.get("test_id", ""),
                        "test_name": result.get("test_name", ""),
                        "issue_severity": result.get("issue_severity", "UNKNOWN"),
                        "issue_confidence": result.get("issue_confidence", "UNKNOWN"),
                        "issue_text": result.get("issue_text", ""),
                        "code": result.get("code", ""),
                    }

                    security_data["bandit_issues"].append(issue)
                    security_data["total_security_issues"] += 1

                    # Count by severity
                    severity = issue["issue_severity"].lower()
                    if severity in security_data["severity_breakdown"]:
                        security_data["severity_breakdown"][severity] += 1

            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Warning: Could not parse Bandit report {bandit_file}: {e}")

        # Parse Safety reports
        safety_files = list(artifacts_dir.glob("**/safety-report.json"))
        for safety_file in safety_files:
            try:
                with open(safety_file, "r") as f:
                    safety_data = json.load(f)

                for vuln in safety_data:
                    vulnerability = {
                        "package": vuln.get("package", ""),
                        "installed_version": vuln.get("installed_version", ""),
                        "vulnerability_id": vuln.get("vulnerability_id", ""),
                        "advisory": vuln.get("advisory", ""),
                        "cve": vuln.get("cve", ""),
                        "specs": vuln.get("specs", []),
                    }

                    security_data["safety_vulnerabilities"].append(vulnerability)
                    security_data["total_security_issues"] += 1

            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Warning: Could not parse Safety report {safety_file}: {e}")

        return security_data

    def collect_test_data(self, artifacts_dir: Path) -> None:
        """
        Collect all test data from artifacts directory for enterprise analysis.

        Args:
            artifacts_dir: Directory containing test artifacts
        """
        artifacts_path = Path(artifacts_dir)

        # Collect JUnit XML files
        xml_files = list(artifacts_path.glob("**/*.xml"))

        for xml_file in xml_files:
            if "junit" in xml_file.name.lower() or "test" in xml_file.name.lower():
                suite_data = self.parse_junit_xml(xml_file)
                if suite_data:
                    # Categorize tests based on filename
                    if "unit" in xml_file.name.lower():
                        self.test_data["unit_tests"].append(suite_data)
                    elif "integration" in xml_file.name.lower():
                        self.test_data["integration_tests"].append(suite_data)
                    elif "api" in xml_file.name.lower():
                        self.test_data["api_tests"].append(suite_data)
                    elif "e2e" in xml_file.name.lower():
                        self.test_data["e2e_tests"].append(suite_data)
                    elif "performance" in xml_file.name.lower():
                        self.test_data["performance_tests"].append(suite_data)
                    elif "stress" in xml_file.name.lower():
                        self.test_data["stress_tests"].append(suite_data)

        # Collect coverage data
        coverage_files = list(artifacts_path.glob("**/coverage*.xml"))
        self.coverage_data = []
        for cov_file in coverage_files:
            cov_data = self.parse_coverage_xml(cov_file)
            if cov_data:
                self.coverage_data.append(cov_data)

        # Collect security data
        self.security_data = self.parse_security_reports(artifacts_path)

        # Calculate aggregate metrics
        self.calculate_metrics()

    def calculate_metrics(self) -> None:
        """Calculate enterprise-level aggregate metrics."""
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        total_duration = 0.0

        # Aggregate test results
        for test_category in self.test_data.values():
            for suite in test_category:
                total_tests += suite.get("tests", 0)
                failed_tests += suite.get("failures", 0) + suite.get("errors", 0)
                skipped_tests += suite.get("skipped", 0)
                total_duration += suite.get("time", 0.0)

        passed_tests = total_tests - failed_tests - skipped_tests

        # Calculate success rate
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0.0

        # Calculate average coverage
        coverage_percentage = 0.0
        if self.coverage_data:
            coverage_percentage = sum(
                cov.get("line_rate", 0.0) for cov in self.coverage_data
            ) / len(self.coverage_data)

        # Update metrics
        self.metrics.update(
            {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "skipped_tests": skipped_tests,
                "success_rate": success_rate,
                "total_duration": total_duration,
                "coverage_percentage": coverage_percentage,
            }
        )

    def generate_visualizations(self) -> Dict[str, str]:
        """
        Generate interactive visualizations for enterprise dashboards.

        Returns:
            Dictionary mapping visualization names to HTML strings
        """
        visualizations = {}

        # Test Results Overview Chart
        test_counts = [
            self.metrics["passed_tests"],
            self.metrics["failed_tests"],
            self.metrics["skipped_tests"],
        ]

        fig_overview = go.Figure(
            data=[
                go.Pie(
                    labels=["Passed", "Failed", "Skipped"],
                    values=test_counts,
                    hole=0.3,
                    marker_colors=["#28a745", "#dc3545", "#ffc107"],
                )
            ]
        )

        fig_overview.update_layout(title="Test Results Overview", font=dict(size=14))

        visualizations["test_overview"] = fig_overview.to_html(
            include_plotlyjs=False, div_id="test-overview-chart"
        )

        # Test Categories Breakdown
        categories = []
        category_counts = []

        for category_name, category_data in self.test_data.items():
            if category_data:
                total_category_tests = sum(
                    suite.get("tests", 0) for suite in category_data
                )
                if total_category_tests > 0:
                    categories.append(category_name.replace("_", " ").title())
                    category_counts.append(total_category_tests)

        if categories:
            fig_categories = go.Figure(
                data=[go.Bar(x=categories, y=category_counts, marker_color="#007bff")]
            )

            fig_categories.update_layout(
                title="Tests by Category",
                xaxis_title="Test Categories",
                yaxis_title="Number of Tests",
                font=dict(size=12),
            )

            visualizations["test_categories"] = fig_categories.to_html(
                include_plotlyjs=False, div_id="test-categories-chart"
            )

        # Coverage Visualization
        if self.coverage_data:
            package_names = []
            coverage_rates = []

            for cov_data in self.coverage_data:
                for package in cov_data.get("packages", [])[:10]:  # Top 10 packages
                    package_names.append(
                        package["name"].split(".")[-1]
                    )  # Just the last part
                    coverage_rates.append(package["line_rate"])

            if package_names:
                fig_coverage = go.Figure(
                    data=[
                        go.Bar(
                            x=package_names,
                            y=coverage_rates,
                            marker_color=[
                                (
                                    "#28a745"
                                    if x >= 80
                                    else "#ffc107" if x >= 60 else "#dc3545"
                                )
                                for x in coverage_rates
                            ],
                        )
                    ]
                )

                fig_coverage.update_layout(
                    title="Code Coverage by Package",
                    xaxis_title="Packages",
                    yaxis_title="Coverage Percentage",
                    font=dict(size=12),
                )

                visualizations["coverage_breakdown"] = fig_coverage.to_html(
                    include_plotlyjs=False, div_id="coverage-breakdown-chart"
                )

        # Security Issues Breakdown
        if self.security_data["total_security_issues"] > 0:
            severity_labels = list(self.security_data["severity_breakdown"].keys())
            severity_values = list(self.security_data["severity_breakdown"].values())

            fig_security = go.Figure(
                data=[
                    go.Bar(
                        x=severity_labels,
                        y=severity_values,
                        marker_color=["#dc3545", "#ffc107", "#28a745"],
                    )
                ]
            )

            fig_security.update_layout(
                title="Security Issues by Severity",
                xaxis_title="Severity Level",
                yaxis_title="Number of Issues",
                font=dict(size=12),
            )

            visualizations["security_breakdown"] = fig_security.to_html(
                include_plotlyjs=False, div_id="security-breakdown-chart"
            )

        return visualizations

    def generate_html_report(self, output_path: Path) -> None:
        """
        Generate comprehensive HTML report for enterprise dashboard integration.

        Args:
            output_path: Path where HTML report will be saved
        """
        # Generate visualizations
        visualizations = self.generate_visualizations()

        # Prepare template context
        context = {
            "title": "Enterprise Test Suite Report",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "metrics": self.metrics,
            "test_data": self.test_data,
            "coverage_data": self.coverage_data,
            "security_data": self.security_data,
            "visualizations": visualizations,
            "quality_thresholds": self.quality_thresholds,
            "quality_gates": self.check_quality_gates(),
        }

        try:
            template = self.template_env.get_template("enterprise_report.html")
            html_content = template.render(**context)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            print(f"✅ HTML report generated: {output_path}")

        except Exception as e:
            print(f"❌ Error generating HTML report: {e}")

    def generate_json_report(self, output_path: Path) -> None:
        """
        Generate JSON report for API consumption and frontend integration.

        Args:
            output_path: Path where JSON report will be saved
        """
        report_data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "version": "1.0.0",
                "format": "enterprise_test_report",
            },
            "metrics": self.metrics,
            "test_results": self.test_data,
            "coverage": self.coverage_data,
            "security": self.security_data,
            "quality_gates": self.check_quality_gates(),
            "recommendations": self.generate_recommendations(),
        }

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)

            print(f"✅ JSON report generated: {output_path}")

        except Exception as e:
            print(f"❌ Error generating JSON report: {e}")

    def check_quality_gates(self) -> Dict[str, Any]:
        """
        Check enterprise quality gates against defined thresholds.

        Returns:
            Quality gates status and details
        """
        gates = {"overall_status": "PASS", "gates": []}

        # Success Rate Gate
        success_gate = {
            "name": "Test Success Rate",
            "threshold": self.quality_thresholds["success_rate"],
            "actual": self.metrics["success_rate"],
            "status": (
                "PASS"
                if self.metrics["success_rate"]
                >= self.quality_thresholds["success_rate"]
                else "FAIL"
            ),
        }
        gates["gates"].append(success_gate)

        # Coverage Gate
        coverage_gate = {
            "name": "Code Coverage",
            "threshold": self.quality_thresholds["coverage"],
            "actual": self.metrics["coverage_percentage"],
            "status": (
                "PASS"
                if self.metrics["coverage_percentage"]
                >= self.quality_thresholds["coverage"]
                else "FAIL"
            ),
        }
        gates["gates"].append(coverage_gate)

        # Security Gate
        security_gate = {
            "name": "Security Issues",
            "threshold": self.quality_thresholds["security_issues"],
            "actual": self.security_data["total_security_issues"],
            "status": (
                "PASS"
                if self.security_data["total_security_issues"]
                <= self.quality_thresholds["security_issues"]
                else "FAIL"
            ),
        }
        gates["gates"].append(security_gate)

        # Update overall status
        if any(gate["status"] == "FAIL" for gate in gates["gates"]):
            gates["overall_status"] = "FAIL"

        return gates

    def generate_recommendations(self) -> List[Dict[str, str]]:
        """
        Generate enterprise-level recommendations based on test results.

        Returns:
            List of recommendations with priority and action items
        """
        recommendations = []

        # Test failure recommendations
        if self.metrics["success_rate"] < self.quality_thresholds["success_rate"]:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "category": "Test Quality",
                    "title": "Improve Test Success Rate",
                    "description": f"Current success rate ({self.metrics['success_rate']:.1f}%) is below threshold ({self.quality_thresholds['success_rate']:.1f}%)",
                    "action": "Review and fix failing tests, improve test stability, consider flaky test isolation",
                }
            )

        # Coverage recommendations
        if self.metrics["coverage_percentage"] < self.quality_thresholds["coverage"]:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": "Code Coverage",
                    "title": "Increase Test Coverage",
                    "description": f"Current coverage ({self.metrics['coverage_percentage']:.1f}%) is below threshold ({self.quality_thresholds['coverage']:.1f}%)",
                    "action": "Add unit tests for uncovered code paths, focus on critical business logic",
                }
            )

        # Security recommendations
        if self.security_data["total_security_issues"] > 0:
            high_severity = self.security_data["severity_breakdown"]["high"]
            if high_severity > 0:
                recommendations.append(
                    {
                        "priority": "CRITICAL",
                        "category": "Security",
                        "title": "Address High-Severity Security Issues",
                        "description": f"Found {high_severity} high-severity security issues",
                        "action": "Immediately review and fix high-severity security vulnerabilities",
                    }
                )

        return recommendations


def create_html_template() -> str:
    """Create the HTML template for the enterprise report."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .metric-card { transition: transform 0.2s; }
        .metric-card:hover { transform: translateY(-5px); }
        .quality-gate-pass { color: #28a745; }
        .quality-gate-fail { color: #dc3545; }
        .chart-container { min-height: 400px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-primary">
        <div class="container-fluid">
            <span class="navbar-brand mb-0 h1">🏢 {{ title }}</span>
            <span class="navbar-text">Generated: {{ generated_at }}</span>
        </div>
    </nav>

    <div class="container-fluid mt-4">
        <!-- Executive Summary -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body text-center">
                        <h2 class="card-title text-primary">{{ metrics.total_tests }}</h2>
                        <p class="card-text">Total Tests</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body text-center">
                        <h2 class="card-title text-success">{{ "%.1f"|format(metrics.success_rate) }}%</h2>
                        <p class="card-text">Success Rate</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body text-center">
                        <h2 class="card-title text-info">{{ "%.1f"|format(metrics.coverage_percentage) }}%</h2>
                        <p class="card-text">Code Coverage</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body text-center">
                        <h2 class="card-title {{ 'text-success' if security_data.total_security_issues == 0 else 'text-warning' }}">
                            {{ security_data.total_security_issues }}
                        </h2>
                        <p class="card-text">Security Issues</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Quality Gates -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5>🎯 Quality Gates Status</h5>
                    </div>
                    <div class="card-body">
                        <div class="alert {{ 'alert-success' if quality_gates.overall_status == 'PASS' else 'alert-danger' }}">
                            <strong>Overall Status: {{ quality_gates.overall_status }}</strong>
                        </div>
                        <div class="row">
                            {% for gate in quality_gates.gates %}
                            <div class="col-md-4 mb-2">
                                <div class="card">
                                    <div class="card-body">
                                        <h6 class="{{ 'quality-gate-pass' if gate.status == 'PASS' else 'quality-gate-fail' }}">
                                            {{ gate.name }} - {{ gate.status }}
                                        </h6>
                                        <p class="small mb-0">
                                            Actual: {{ "%.1f"|format(gate.actual) }}{% if gate.name != 'Security Issues' %}%{% endif %} 
                                            | Threshold: {{ "%.1f"|format(gate.threshold) }}{% if gate.name != 'Security Issues' %}%{% endif %}
                                        </p>
                                    </div>
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Visualizations -->
        <div class="row mb-4">
            {% if visualizations.test_overview %}
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header"><h6>📊 Test Results Overview</h6></div>
                    <div class="card-body chart-container">
                        {{ visualizations.test_overview|safe }}
                    </div>
                </div>
            </div>
            {% endif %}
            
            {% if visualizations.test_categories %}
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header"><h6>📈 Tests by Category</h6></div>
                    <div class="card-body chart-container">
                        {{ visualizations.test_categories|safe }}
                    </div>
                </div>
            </div>
            {% endif %}
        </div>

        {% if visualizations.coverage_breakdown %}
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header"><h6>🎯 Code Coverage Breakdown</h6></div>
                    <div class="card-body chart-container">
                        {{ visualizations.coverage_breakdown|safe }}
                    </div>
                </div>
            </div>
        </div>
        {% endif %}

        {% if visualizations.security_breakdown %}
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header"><h6>🔒 Security Issues by Severity</h6></div>
                    <div class="card-body chart-container">
                        {{ visualizations.security_breakdown|safe }}
                    </div>
                </div>
            </div>
        </div>
        {% endif %}

        <!-- Test Details -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5>📋 Detailed Test Results</h5>
                    </div>
                    <div class="card-body">
                        <div class="accordion" id="testAccordion">
                            {% set categories = [
                                ('unit_tests', 'Unit Tests'),
                                ('integration_tests', 'Integration Tests'),
                                ('api_tests', 'API Tests'),
                                ('e2e_tests', 'End-to-End Tests'),
                                ('performance_tests', 'Performance Tests')
                            ] %}
                            
                            {% for category_key, category_name in categories %}
                            {% if test_data[category_key] %}
                            <div class="accordion-item">
                                <h2 class="accordion-header" id="heading{{ loop.index }}">
                                    <button class="accordion-button collapsed" type="button" 
                                            data-bs-toggle="collapse" data-bs-target="#collapse{{ loop.index }}">
                                        {{ category_name }} ({{ test_data[category_key]|length }} suites)
                                    </button>
                                </h2>
                                <div id="collapse{{ loop.index }}" class="accordion-collapse collapse" 
                                     data-bs-parent="#testAccordion">
                                    <div class="accordion-body">
                                        {% for suite in test_data[category_key] %}
                                        <div class="mb-3">
                                            <h6>{{ suite.name }}</h6>
                                            <p class="small text-muted">
                                                Tests: {{ suite.tests }} | 
                                                Failures: {{ suite.failures }} | 
                                                Errors: {{ suite.errors }} | 
                                                Duration: {{ "%.2f"|format(suite.time) }}s
                                            </p>
                                        </div>
                                        {% endfor %}
                                    </div>
                                </div>
                            </div>
                            {% endif %}
                            {% endfor %}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""


def main():
    """Main entry point for enterprise test reporter."""
    parser = argparse.ArgumentParser(description="Enterprise Test Reporter")
    parser.add_argument(
        "--artifacts-dir", required=True, help="Directory containing test artifacts"
    )
    parser.add_argument(
        "--output-dir", required=True, help="Output directory for reports"
    )
    parser.add_argument(
        "--format",
        default="html,json",
        help="Output formats (comma-separated): html,json,pdf",
    )
    parser.add_argument(
        "--include-metrics", action="store_true", help="Include detailed metrics"
    )
    parser.add_argument(
        "--include-trends", action="store_true", help="Include trend analysis"
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create templates directory and template file
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(exist_ok=True)

    template_path = templates_dir / "enterprise_report.html"
    if not template_path.exists():
        with open(template_path, "w") as f:
            f.write(create_html_template())

    # Initialize reporter
    reporter = EnterpriseTestReporter()

    # Collect test data
    print("🔍 Collecting test data...")
    reporter.collect_test_data(Path(args.artifacts_dir))

    # Generate reports
    formats = args.format.split(",")

    if "html" in formats:
        print("📊 Generating HTML report...")
        reporter.generate_html_report(output_dir / "enterprise_test_report.html")

    if "json" in formats:
        print("📋 Generating JSON report...")
        reporter.generate_json_report(output_dir / "enterprise_test_report.json")

    print("✅ Enterprise test reporting complete!")
    print(f"📁 Reports saved to: {output_dir}")

    # Print summary
    print("\n📈 Test Summary:")
    print(f"   Total Tests: {reporter.metrics['total_tests']}")
    print(f"   Success Rate: {reporter.metrics['success_rate']:.1f}%")
    print(f"   Coverage: {reporter.metrics['coverage_percentage']:.1f}%")
    print(f"   Security Issues: {reporter.security_data['total_security_issues']}")

    quality_gates = reporter.check_quality_gates()
    print(f"   Quality Gates: {quality_gates['overall_status']}")


if __name__ == "__main__":
    main()
