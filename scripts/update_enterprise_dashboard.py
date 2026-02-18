#!/usr/bin/env python3
"""
Enterprise Dashboard Update Script
=================================

This script provides seamless integration between the testing suite and
the tools frontend dashboard, enabling real-time test visibility and
comprehensive quality metrics for stakeholders.

Features:
- Real-time dashboard updates
- API endpoints for frontend consumption
- WebSocket support for live updates
- Comprehensive test metrics aggregation
- Historical trend analysis
- Interactive visualizations
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Third-party imports
import pandas as pd
import requests
import websockets
import yaml
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit


class DashboardUpdater:
    """
    Enterprise dashboard updater with frontend integration capabilities.
    """

    def __init__(self, config_file: Optional[Path] = None):
        self.config = self.load_config(config_file)
        self.app = Flask(__name__)
        self.app.config["SECRET_KEY"] = self.config.get("secret_key", "dev-secret-key")

        CORS(self.app)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        self.setup_logging()
        self.setup_routes()
        self.setup_websocket_handlers()

        # Data storage
        self.current_metrics = {}
        self.historical_data = []
        self.connected_clients = set()

    def load_config(self, config_file: Optional[Path]) -> Dict[str, Any]:
        """Load dashboard configuration."""
        default_config = {
            "host": "0.0.0.0",
            "port": 8080,
            "debug": False,
            "frontend_url": "http://localhost:3000",
            "update_interval": 30,  # seconds
            "retention_days": 30,
            "websocket_enabled": True,
            "api_endpoints": {
                "metrics": "/api/v1/metrics",
                "health": "/api/v1/health",
                "trends": "/api/v1/trends",
                "reports": "/api/v1/reports",
            },
        }

        if config_file and config_file.exists():
            try:
                with open(config_file, "r") as f:
                    user_config = yaml.safe_load(f)
                    default_config.update(user_config)
            except Exception as e:
                logging.warning(f"Could not load config file {config_file}: {e}")

        return default_config

    def setup_logging(self):
        """Set up logging configuration."""
        logging.basicConfig(
            level=logging.INFO if not self.config["debug"] else logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

    def setup_routes(self):
        """Set up Flask API routes for frontend integration."""

        @self.app.route("/")
        def dashboard_home():
            """Main dashboard route."""
            return render_template("dashboard.html")

        @self.app.route("/api/v1/health")
        def health_check():
            """Health check endpoint."""
            return jsonify(
                {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0.0",
                    "uptime": self.get_uptime(),
                }
            )

        @self.app.route("/api/v1/metrics")
        def get_current_metrics():
            """Get current test metrics."""
            return jsonify(
                {
                    "data": self.current_metrics,
                    "timestamp": datetime.now().isoformat(),
                    "status": "success",
                }
            )

        @self.app.route("/api/v1/trends")
        def get_trends():
            """Get historical trends data."""
            days = request.args.get("days", 7, type=int)
            metrics = self.calculate_trends(days)

            return jsonify(
                {
                    "data": metrics,
                    "period_days": days,
                    "timestamp": datetime.now().isoformat(),
                    "status": "success",
                }
            )

        @self.app.route("/api/v1/reports")
        def get_reports():
            """Get available test reports."""
            reports = self.get_available_reports()

            return jsonify(
                {
                    "data": reports,
                    "count": len(reports),
                    "timestamp": datetime.now().isoformat(),
                    "status": "success",
                }
            )

        @self.app.route("/api/v1/reports/<report_id>")
        def get_report_details(report_id):
            """Get detailed report information."""
            report = self.get_report_by_id(report_id)

            if not report:
                return jsonify({"error": "Report not found", "status": "error"}), 404

            return jsonify(
                {
                    "data": report,
                    "timestamp": datetime.now().isoformat(),
                    "status": "success",
                }
            )

        @self.app.route("/api/v1/quality-gates")
        def get_quality_gates():
            """Get current quality gates status."""
            quality_gates = self.get_quality_gates_status()

            return jsonify(
                {
                    "data": quality_gates,
                    "timestamp": datetime.now().isoformat(),
                    "status": "success",
                }
            )

    def setup_websocket_handlers(self):
        """Set up WebSocket handlers for real-time updates."""

        @self.socketio.on("connect")
        def handle_connect():
            """Handle client connection."""
            client_id = request.sid
            self.connected_clients.add(client_id)
            self.logger.info(f"Client {client_id} connected")

            # Send current metrics to new client
            emit(
                "metrics_update",
                {"data": self.current_metrics, "timestamp": datetime.now().isoformat()},
            )

        @self.socketio.on("disconnect")
        def handle_disconnect():
            """Handle client disconnection."""
            client_id = request.sid
            self.connected_clients.discard(client_id)
            self.logger.info(f"Client {client_id} disconnected")

        @self.socketio.on("request_metrics")
        def handle_metrics_request():
            """Handle metrics request from client."""
            emit(
                "metrics_update",
                {"data": self.current_metrics, "timestamp": datetime.now().isoformat()},
            )

        @self.socketio.on("request_trends")
        def handle_trends_request(data):
            """Handle trends request from client."""
            days = data.get("days", 7)
            trends = self.calculate_trends(days)

            emit(
                "trends_update",
                {
                    "data": trends,
                    "period_days": days,
                    "timestamp": datetime.now().isoformat(),
                },
            )

    def update_metrics(self, reports_dir: Path):
        """Update dashboard metrics from test reports."""
        try:
            # Load enterprise test report
            report_file = reports_dir / "enterprise_test_report.json"
            if not report_file.exists():
                self.logger.warning(f"Report file not found: {report_file}")
                return

            with open(report_file, "r") as f:
                report_data = json.load(f)

            # Extract key metrics
            metrics = self.extract_dashboard_metrics(report_data)

            # Update current metrics
            self.current_metrics = metrics

            # Store historical data
            self.store_historical_data(metrics)

            # Broadcast to connected clients
            if self.config["websocket_enabled"]:
                self.broadcast_metrics_update(metrics)

            self.logger.info("Dashboard metrics updated successfully")

        except Exception as e:
            self.logger.error(f"Error updating metrics: {e}")

    def extract_dashboard_metrics(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key metrics for dashboard display."""
        metrics = report_data.get("metrics", {})
        quality_gates = report_data.get("quality_gates", {})
        recommendations = report_data.get("recommendations", [])

        return {
            "overview": {
                "total_tests": metrics.get("total_tests", 0),
                "success_rate": round(metrics.get("success_rate", 0), 1),
                "coverage_percentage": round(metrics.get("coverage_percentage", 0), 1),
                "failed_tests": metrics.get("failed_tests", 0),
                "duration": round(metrics.get("total_duration", 0), 2),
            },
            "quality_gates": {
                "overall_status": quality_gates.get("overall_status", "UNKNOWN"),
                "passed_gates": len(quality_gates.get("passed_gates", [])),
                "failed_gates": len(quality_gates.get("failed_gates", [])),
                "warning_gates": len(quality_gates.get("warning_gates", [])),
            },
            "security": self.extract_security_metrics(report_data),
            "performance": self.extract_performance_metrics(report_data),
            "trends": self.calculate_metric_trends(metrics),
            "recommendations": {
                "critical": len(
                    [r for r in recommendations if r.get("priority") == "CRITICAL"]
                ),
                "high": len(
                    [r for r in recommendations if r.get("priority") == "HIGH"]
                ),
                "medium": len(
                    [r for r in recommendations if r.get("priority") == "MEDIUM"]
                ),
                "total": len(recommendations),
            },
            "last_updated": datetime.now().isoformat(),
        }

    def extract_security_metrics(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract security metrics from report data."""
        security = report_data.get("security", {})

        return {
            "total_issues": security.get("total_security_issues", 0),
            "critical_issues": security.get("critical_security_issues", 0),
            "high_issues": security.get("high_security_issues", 0),
            "medium_issues": security.get("medium_security_issues", 0),
            "low_issues": security.get("low_security_issues", 0),
            "security_score": round(security.get("security_score", 100), 1),
            "compliance_status": security.get("compliance_status", "compliant"),
        }

    def extract_performance_metrics(
        self, report_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract performance metrics from report data."""
        # This would extract performance data from the detailed analysis
        return {
            "average_response_time": 0.0,
            "peak_memory_usage": 0.0,
            "slow_tests_count": 0,
            "performance_regression": 0.0,
        }

    def calculate_metric_trends(
        self, current_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate trends for key metrics."""
        if len(self.historical_data) < 2:
            return {
                "success_rate": "stable",
                "coverage": "stable",
                "duration": "stable",
            }

        # Compare with previous data point
        previous = (
            self.historical_data[-2]
            if len(self.historical_data) >= 2
            else self.historical_data[-1]
        )

        return {
            "success_rate": self.calculate_trend(
                current_metrics.get("success_rate", 0),
                previous["overview"]["success_rate"],
            ),
            "coverage": self.calculate_trend(
                current_metrics.get("coverage_percentage", 0),
                previous["overview"]["coverage_percentage"],
            ),
            "duration": self.calculate_trend(
                current_metrics.get("total_duration", 0),
                previous["overview"]["duration"],
                inverse=True,  # Lower duration is better
            ),
        }

    def calculate_trend(
        self, current: float, previous: float, inverse: bool = False
    ) -> str:
        """Calculate trend direction for a metric."""
        if abs(current - previous) < 0.1:  # Threshold for stable
            return "stable"

        if inverse:
            return "improving" if current < previous else "degrading"
        else:
            return "improving" if current > previous else "degrading"

    def store_historical_data(self, metrics: Dict[str, Any]):
        """Store metrics for historical analysis."""
        # Add timestamp
        metrics["timestamp"] = datetime.now().isoformat()

        # Add to historical data
        self.historical_data.append(metrics)

        # Cleanup old data
        cutoff_date = datetime.now() - timedelta(days=self.config["retention_days"])
        self.historical_data = [
            data
            for data in self.historical_data
            if datetime.fromisoformat(data["timestamp"]) > cutoff_date
        ]

    def calculate_trends(self, days: int) -> Dict[str, Any]:
        """Calculate trends for the specified number of days."""
        cutoff_date = datetime.now() - timedelta(days=days)

        # Filter data for the specified period
        period_data = [
            data
            for data in self.historical_data
            if datetime.fromisoformat(data["timestamp"]) > cutoff_date
        ]

        if not period_data:
            return {"message": "No data available for the specified period"}

        # Calculate trends
        success_rates = [data["overview"]["success_rate"] for data in period_data]
        coverage_rates = [
            data["overview"]["coverage_percentage"] for data in period_data
        ]
        durations = [data["overview"]["duration"] for data in period_data]
        timestamps = [data["timestamp"] for data in period_data]

        return {
            "period": {
                "days": days,
                "start_date": period_data[0]["timestamp"],
                "end_date": period_data[-1]["timestamp"],
            },
            "trends": {
                "success_rate": {
                    "data": success_rates,
                    "timestamps": timestamps,
                    "trend": self.calculate_overall_trend(success_rates),
                    "min": min(success_rates),
                    "max": max(success_rates),
                    "average": round(sum(success_rates) / len(success_rates), 1),
                },
                "coverage": {
                    "data": coverage_rates,
                    "timestamps": timestamps,
                    "trend": self.calculate_overall_trend(coverage_rates),
                    "min": min(coverage_rates),
                    "max": max(coverage_rates),
                    "average": round(sum(coverage_rates) / len(coverage_rates), 1),
                },
                "duration": {
                    "data": durations,
                    "timestamps": timestamps,
                    "trend": self.calculate_overall_trend(durations, inverse=True),
                    "min": min(durations),
                    "max": max(durations),
                    "average": round(sum(durations) / len(durations), 2),
                },
            },
        }

    def calculate_overall_trend(
        self, values: List[float], inverse: bool = False
    ) -> str:
        """Calculate overall trend for a series of values."""
        if len(values) < 2:
            return "stable"

        # Simple linear trend calculation
        first_half = sum(values[: len(values) // 2]) / (len(values) // 2)
        second_half = sum(values[len(values) // 2 :]) / (len(values) - len(values) // 2)

        diff_percentage = abs(second_half - first_half) / first_half * 100

        if diff_percentage < 5:  # Less than 5% change is considered stable
            return "stable"

        if inverse:
            return "improving" if second_half < first_half else "degrading"
        else:
            return "improving" if second_half > first_half else "degrading"

    def broadcast_metrics_update(self, metrics: Dict[str, Any]):
        """Broadcast metrics update to all connected clients."""
        if self.connected_clients:
            self.socketio.emit(
                "metrics_update",
                {"data": metrics, "timestamp": datetime.now().isoformat()},
            )
            self.logger.debug(
                f"Broadcasted metrics to {len(self.connected_clients)} clients"
            )

    def get_available_reports(self) -> List[Dict[str, Any]]:
        """Get list of available test reports."""
        # This would scan the reports directory for available reports
        return [
            {
                "id": "latest",
                "name": "Latest Test Report",
                "type": "enterprise",
                "generated_at": datetime.now().isoformat(),
                "status": "completed",
            }
        ]

    def get_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get specific report by ID."""
        if report_id == "latest":
            return {
                "id": "latest",
                "name": "Latest Test Report",
                "metrics": self.current_metrics,
                "generated_at": datetime.now().isoformat(),
            }
        return None

    def get_quality_gates_status(self) -> Dict[str, Any]:
        """Get current quality gates status."""
        return self.current_metrics.get(
            "quality_gates",
            {
                "overall_status": "UNKNOWN",
                "passed_gates": 0,
                "failed_gates": 0,
                "warning_gates": 0,
            },
        )

    def get_uptime(self) -> str:
        """Get service uptime."""
        # This would calculate actual uptime
        return "00:00:00"

    def push_to_frontend(self, frontend_url: str):
        """Push metrics to external frontend via HTTP API."""
        try:
            response = requests.post(
                f"{frontend_url}/api/test-metrics",
                json=self.current_metrics,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 200:
                self.logger.info("Successfully pushed metrics to frontend")
            else:
                self.logger.warning(f"Failed to push metrics: {response.status_code}")

        except requests.RequestException as e:
            self.logger.error(f"Error pushing to frontend: {e}")

    def run_server(self):
        """Run the dashboard server."""
        self.logger.info(
            f"Starting dashboard server on {self.config['host']}:{self.config['port']}"
        )

        self.socketio.run(
            self.app,
            host=self.config["host"],
            port=self.config["port"],
            debug=self.config["debug"],
        )

    async def start_background_updates(self, reports_dir: Path):
        """Start background task for periodic updates."""
        while True:
            try:
                self.update_metrics(reports_dir)

                # Push to external frontend if configured
                if self.config.get("frontend_url"):
                    self.push_to_frontend(self.config["frontend_url"])

                await asyncio.sleep(self.config["update_interval"])

            except Exception as e:
                self.logger.error(f"Error in background update: {e}")
                await asyncio.sleep(self.config["update_interval"])


def create_dashboard_template():
    """Create a basic HTML template for the dashboard."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enterprise Testing Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .metric-card { transition: transform 0.2s; margin-bottom: 1rem; }
        .metric-card:hover { transform: translateY(-2px); }
        .status-pass { color: #28a745; }
        .status-fail { color: #dc3545; }
        .status-warning { color: #ffc107; }
        .trend-improving { color: #28a745; }
        .trend-degrading { color: #dc3545; }
        .trend-stable { color: #6c757d; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-primary">
        <div class="container-fluid">
            <span class="navbar-brand">🏢 Enterprise Testing Dashboard</span>
            <span class="navbar-text" id="last-updated">Loading...</span>
        </div>
    </nav>

    <div class="container-fluid mt-4">
        <!-- Overview Cards -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body text-center">
                        <h3 class="card-title text-primary" id="total-tests">-</h3>
                        <p class="card-text">Total Tests</p>
                        <small class="text-muted" id="trend-tests">-</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body text-center">
                        <h3 class="card-title text-success" id="success-rate">-%</h3>
                        <p class="card-text">Success Rate</p>
                        <small class="text-muted" id="trend-success">-</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body text-center">
                        <h3 class="card-title text-info" id="coverage">-%</h3>
                        <p class="card-text">Code Coverage</p>
                        <small class="text-muted" id="trend-coverage">-</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card metric-card">
                    <div class="card-body text-center">
                        <h3 class="card-title" id="quality-status">-</h3>
                        <p class="card-text">Quality Gates</p>
                        <small class="text-muted" id="gates-summary">-</small>
                    </div>
                </div>
            </div>
        </div>

        <!-- Charts Row -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header"><h6>Test Results Trend</h6></div>
                    <div class="card-body">
                        <div id="success-trend-chart" style="height: 300px;"></div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header"><h6>Coverage Trend</h6></div>
                    <div class="card-body">
                        <div id="coverage-trend-chart" style="height: 300px;"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Security and Performance -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header"><h6>Security Status</h6></div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-6">
                                <h4 id="security-score" class="text-success">100</h4>
                                <small>Security Score</small>
                            </div>
                            <div class="col-6">
                                <h4 id="security-issues" class="text-warning">0</h4>
                                <small>Total Issues</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header"><h6>Recommendations</h6></div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-3">
                                <h5 id="rec-critical" class="text-danger">0</h5>
                                <small>Critical</small>
                            </div>
                            <div class="col-3">
                                <h5 id="rec-high" class="text-warning">0</h5>
                                <small>High</small>
                            </div>
                            <div class="col-3">
                                <h5 id="rec-medium" class="text-info">0</h5>
                                <small>Medium</small>
                            </div>
                            <div class="col-3">
                                <h5 id="rec-total" class="text-muted">0</h5>
                                <small>Total</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Initialize Socket.IO connection
        const socket = io();
        
        // Handle metrics updates
        socket.on('metrics_update', function(data) {
            updateDashboard(data.data);
            document.getElementById('last-updated').textContent = 
                'Updated: ' + new Date(data.timestamp).toLocaleTimeString();
        });
        
        // Update dashboard elements
        function updateDashboard(metrics) {
            const overview = metrics.overview || {};
            const qualityGates = metrics.quality_gates || {};
            const security = metrics.security || {};
            const recommendations = metrics.recommendations || {};
            const trends = metrics.trends || {};
            
            // Update overview cards
            document.getElementById('total-tests').textContent = overview.total_tests || 0;
            document.getElementById('success-rate').textContent = (overview.success_rate || 0) + '%';
            document.getElementById('coverage').textContent = (overview.coverage_percentage || 0) + '%';
            
            // Update quality gates
            const statusElement = document.getElementById('quality-status');
            statusElement.textContent = qualityGates.overall_status || 'UNKNOWN';
            statusElement.className = 'card-title status-' + (qualityGates.overall_status || 'unknown').toLowerCase();
            
            document.getElementById('gates-summary').textContent = 
                `${qualityGates.passed_gates || 0} passed, ${qualityGates.failed_gates || 0} failed`;
            
            // Update trends
            updateTrendIndicator('trend-success', trends.success_rate);
            updateTrendIndicator('trend-coverage', trends.coverage);
            
            // Update security
            document.getElementById('security-score').textContent = security.security_score || 100;
            document.getElementById('security-issues').textContent = security.total_issues || 0;
            
            // Update recommendations
            document.getElementById('rec-critical').textContent = recommendations.critical || 0;
            document.getElementById('rec-high').textContent = recommendations.high || 0;
            document.getElementById('rec-medium').textContent = recommendations.medium || 0;
            document.getElementById('rec-total').textContent = recommendations.total || 0;
        }
        
        function updateTrendIndicator(elementId, trend) {
            const element = document.getElementById(elementId);
            element.textContent = trend || 'stable';
            element.className = 'text-muted trend-' + (trend || 'stable');
        }
        
        // Request initial data
        socket.emit('request_metrics');
        
        // Periodic trend data requests
        setInterval(() => {
            socket.emit('request_trends', {days: 7});
        }, 60000); // Every minute
    </script>
</body>
</html>"""


def main():
    """Main entry point for dashboard updater."""
    parser = argparse.ArgumentParser(description="Enterprise Dashboard Updater")
    parser.add_argument(
        "--reports-dir", required=True, help="Directory containing test reports"
    )
    parser.add_argument("--dashboard-config", help="Dashboard configuration file")
    parser.add_argument(
        "--push-to-frontend",
        action="store_true",
        help="Push metrics to external frontend",
    )
    parser.add_argument(
        "--server-mode", action="store_true", help="Run as dashboard server"
    )

    args = parser.parse_args()

    # Initialize dashboard updater
    config_file = Path(args.dashboard_config) if args.dashboard_config else None
    updater = DashboardUpdater(config_file)

    # Create templates directory if running as server
    if args.server_mode:
        templates_dir = Path(__file__).parent.parent / "templates"
        templates_dir.mkdir(exist_ok=True)

        template_file = templates_dir / "dashboard.html"
        if not template_file.exists():
            with open(template_file, "w") as f:
                f.write(create_dashboard_template())

    if args.server_mode:
        # Run as dashboard server with background updates
        reports_dir = Path(args.reports_dir)

        import threading

        # Start background updates in a separate thread
        def background_updates():
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(updater.start_background_updates(reports_dir))

        thread = threading.Thread(target=background_updates, daemon=True)
        thread.start()

        # Run dashboard server
        updater.run_server()
    else:
        # Single update mode
        print("📊 Updating dashboard metrics...")
        updater.update_metrics(Path(args.reports_dir))

        if args.push_to_frontend and updater.config.get("frontend_url"):
            print("🚀 Pushing metrics to frontend...")
            updater.push_to_frontend(updater.config["frontend_url"])

        print("✅ Dashboard update complete!")


if __name__ == "__main__":
    main()
