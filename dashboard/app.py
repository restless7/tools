"""
Testing Suite Dashboard - Flask Backend
========================================

Web dashboard for real-time test monitoring, logging, and results visualization.
"""

import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_from_directory,
)
from flask_cors import CORS

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from test_logger import get_logger

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# Configuration
BASE_DIR = Path(__file__).parent.parent
TESTS_DIR = BASE_DIR / "tests"
LOGS_DIR = BASE_DIR / "logs"
REPORTS_DIR = BASE_DIR / "reports"
COVERAGE_DIR = BASE_DIR / "htmlcov"

# Initialize logger
logger = get_logger("dashboard")

# In-memory storage for test runs
test_runs = deque(maxlen=50)  # Keep last 50 runs
current_test_run = {
    "running": False,
    "start_time": None,
    "tests": [],
    "logs": deque(maxlen=1000),  # Keep last 1000 log lines
}


class TestRunner:
    """Manages test execution in background."""

    def __init__(self):
        self.process = None
        self.thread = None
        self.running = False

    def run_tests(
        self,
        test_path: str = "tests/",
        markers: List[str] = None,
        coverage: bool = True,
    ):
        """Run tests in background thread."""
        if self.running:
            return {"error": "Tests already running"}

        self.running = True
        current_test_run["running"] = True
        current_test_run["start_time"] = datetime.now().isoformat()
        current_test_run["tests"] = []
        current_test_run["logs"].clear()

        def execute():
            try:
                # Build pytest command
                cmd = ["venv/bin/pytest", test_path, "-v", "--tb=short"]

                if coverage:
                    cmd.extend(
                        ["--cov=ice_pipeline", "--cov-report=html", "--cov-report=json"]
                    )

                if markers:
                    for marker in markers:
                        cmd.extend(["-m", marker])

                # Add JSON report
                cmd.extend(
                    ["--json-report", "--json-report-file=reports/test_report.json"]
                )

                logger.info(f"Running tests: {' '.join(cmd)}")
                current_test_run["logs"].append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "level": "INFO",
                        "message": f"Starting test execution: {' '.join(cmd)}",
                    }
                )

                # Execute tests
                self.process = subprocess.Popen(
                    cmd,
                    cwd=str(BASE_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )

                # Stream output
                for line in self.process.stdout:
                    line = line.strip()
                    if line:
                        current_test_run["logs"].append(
                            {
                                "timestamp": datetime.now().isoformat(),
                                "level": "INFO",
                                "message": line,
                            }
                        )
                        logger.debug(line)

                # Wait for completion
                self.process.wait()

                # Parse results
                self._parse_results()

                logger.info("Test execution completed")
                current_test_run["logs"].append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "level": "INFO",
                        "message": "Test execution completed",
                    }
                )

            except Exception as e:
                logger.error(f"Test execution failed: {e}", exc_info=True)
                current_test_run["logs"].append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "level": "ERROR",
                        "message": f"Test execution failed: {str(e)}",
                    }
                )
            finally:
                self.running = False
                current_test_run["running"] = False

                # Save run history
                test_runs.append(
                    {
                        "timestamp": current_test_run["start_time"],
                        "duration": (
                            datetime.now()
                            - datetime.fromisoformat(current_test_run["start_time"])
                        ).total_seconds(),
                        "tests": len(current_test_run["tests"]),
                        "passed": sum(
                            1
                            for t in current_test_run["tests"]
                            if t.get("outcome") == "passed"
                        ),
                        "failed": sum(
                            1
                            for t in current_test_run["tests"]
                            if t.get("outcome") == "failed"
                        ),
                    }
                )

        # Start execution thread
        self.thread = threading.Thread(target=execute)
        self.thread.start()

        return {"status": "started"}

    def _parse_results(self):
        """Parse test results from JSON report."""
        try:
            report_file = REPORTS_DIR / "test_report.json"
            if report_file.exists():
                with open(report_file) as f:
                    data = json.load(f)
                    current_test_run["tests"] = data.get("tests", [])

                    # Add summary
                    summary = data.get("summary", {})
                    current_test_run["logs"].append(
                        {
                            "timestamp": datetime.now().isoformat(),
                            "level": "INFO",
                            "message": f"Results: {summary.get('passed', 0)} passed, {summary.get('failed', 0)} failed",
                        }
                    )
        except Exception as e:
            logger.error(f"Failed to parse results: {e}")

    def stop(self):
        """Stop running tests."""
        if self.process and self.running:
            self.process.terminate()
            self.running = False
            current_test_run["running"] = False
            return {"status": "stopped"}
        return {"status": "not_running"}


# Global test runner
test_runner = TestRunner()


# Routes
@app.route("/")
def index():
    """Dashboard home page."""
    return render_template("index.html")


@app.route("/api/status")
def get_status():
    """Get current test execution status."""
    return jsonify(
        {
            "running": current_test_run["running"],
            "start_time": current_test_run["start_time"],
            "tests_count": len(current_test_run["tests"]),
            "logs_count": len(current_test_run["logs"]),
        }
    )


@app.route("/api/tests/run", methods=["POST"])
def run_tests():
    """Trigger test execution."""
    data = request.json or {}
    test_path = data.get("path", "tests/")
    markers = data.get("markers", [])
    coverage = data.get("coverage", True)

    result = test_runner.run_tests(test_path, markers, coverage)
    return jsonify(result)


@app.route("/api/tests/stop", methods=["POST"])
def stop_tests():
    """Stop test execution."""
    result = test_runner.stop()
    return jsonify(result)


@app.route("/api/tests/results")
def get_test_results():
    """Get current test results."""
    return jsonify(
        {
            "running": current_test_run["running"],
            "start_time": current_test_run["start_time"],
            "tests": list(current_test_run["tests"]),
            "summary": {
                "total": len(current_test_run["tests"]),
                "passed": sum(
                    1 for t in current_test_run["tests"] if t.get("outcome") == "passed"
                ),
                "failed": sum(
                    1 for t in current_test_run["tests"] if t.get("outcome") == "failed"
                ),
                "skipped": sum(
                    1
                    for t in current_test_run["tests"]
                    if t.get("outcome") == "skipped"
                ),
            },
        }
    )


@app.route("/api/logs")
def get_logs():
    """Get test execution logs."""
    limit = request.args.get("limit", 100, type=int)
    logs = list(current_test_run["logs"])[-limit:]
    return jsonify({"logs": logs})


@app.route("/api/logs/stream")
def stream_logs():
    """Stream logs in real-time using Server-Sent Events."""

    def generate():
        last_index = 0
        while True:
            logs = list(current_test_run["logs"])
            if len(logs) > last_index:
                for log in logs[last_index:]:
                    yield f"data: {json.dumps(log)}\n\n"
                last_index = len(logs)
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/coverage")
def get_coverage():
    """Get coverage data."""
    try:
        coverage_json = REPORTS_DIR / "coverage.json"
        if coverage_json.exists():
            with open(coverage_json) as f:
                data = json.load(f)
                return jsonify(data)
        return jsonify({"error": "Coverage data not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/coverage/html")
def coverage_html():
    """Redirect to coverage HTML report."""
    index_file = COVERAGE_DIR / "index.html"
    if index_file.exists():
        return send_from_directory(str(COVERAGE_DIR), "index.html")
    return jsonify({"error": "Coverage HTML not found"}), 404


@app.route("/api/history")
def get_history():
    """Get test run history."""
    return jsonify({"runs": list(test_runs)})


@app.route("/api/stats")
def get_stats():
    """Get overall statistics."""
    if not test_runs:
        return jsonify({"error": "No test runs yet"}), 404

    recent_runs = list(test_runs)[-10:]

    stats = {
        "total_runs": len(test_runs),
        "last_run": recent_runs[-1] if recent_runs else None,
        "average_duration": sum(r["duration"] for r in recent_runs) / len(recent_runs),
        "average_pass_rate": sum(r["passed"] / max(r["tests"], 1) for r in recent_runs)
        * 100
        / len(recent_runs),
        "trend": {
            "durations": [r["duration"] for r in recent_runs],
            "pass_rates": [r["passed"] / max(r["tests"], 1) * 100 for r in recent_runs],
            "timestamps": [r["timestamp"] for r in recent_runs],
        },
    }

    return jsonify(stats)


@app.route("/api/health")
def health():
    """Health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "tests_running": current_test_run["running"],
        }
    )


if __name__ == "__main__":
    logger.info("Starting Testing Suite Dashboard")
    logger.info(f"Dashboard URL: http://localhost:5000")

    # Ensure directories exist
    LOGS_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    host = os.getenv("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_RUN_PORT", "5000"))

    # Start Flask app
    app.run(host=host, port=port, debug=debug, threaded=True)
