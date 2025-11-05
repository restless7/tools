# Testing Suite Dashboard

A comprehensive, real-time dashboard for monitoring and controlling the Enterprise Tools Platform testing suite.

## Features

### 🎯 Core Capabilities
- **One-Click Test Execution**: Run all tests, unit tests only, or API tests only
- **Real-Time Monitoring**: Live test logs streaming via Server-Sent Events
- **Coverage Visualization**: Interactive coverage meter with detailed breakdown
- **Performance Tracking**: Test duration and performance metrics
- **Test History**: Track last 50 test runs with trend analysis
- **Beautiful UI**: Modern purple gradient theme with responsive design

### 📊 Dashboard Sections

#### 1. Control Panel
- **Run All Tests**: Execute the complete test suite
- **Run Unit Tests**: Execute only unit tests (`tests/unit/`)
- **Run API Tests**: Execute only API tests (`tests/api/`)
- **Stop**: Terminate running tests
- **Refresh**: Reload all data

#### 2. Real-Time Stats
- **Test Results**: Passed, failed, error counts with pass rate percentage
- **Coverage Meter**: Circular visualization of code coverage
- **Performance**: Total test duration
- **Status Badge**: Current test run state (idle, running, passed, failed)

#### 3. Tabbed Interface
- **Live Logs**: Real-time test output with color-coded log levels
- **Test Results**: Detailed test outcome breakdown
- **History**: Last 50 test runs with sortable columns

## Quick Start

### Option 1: Using the Startup Script (Recommended)

```bash
# From the tools directory
chmod +x start_dashboard.sh
./start_dashboard.sh
```

The script will:
1. Check/create virtual environment
2. Install all dependencies
3. Create required directories
4. Start the dashboard at http://localhost:5000

### Option 2: Manual Start

```bash
# Activate virtual environment
source venv/bin/activate

# Install dashboard dependencies
pip install -r dashboard/requirements.txt

# Ensure directories exist
mkdir -p logs reports

# Start the dashboard
python dashboard/app.py
```

### Option 3: Direct Python

```bash
# From the tools directory
source venv/bin/activate
cd dashboard
python app.py
```

## Using the Dashboard

### Running Tests

1. **Open Dashboard**: Navigate to http://localhost:5000 in your browser
2. **Choose Test Type**: Click one of the run buttons:
   - "Run All Tests" - Complete test suite
   - "Run Unit Tests" - Unit tests only
   - "Run API Tests" - API endpoint tests only
3. **Watch Progress**: See live logs in the "Live Logs" tab
4. **Review Results**: Check results in the "Test Results" tab

### Monitoring Logs

- **Live Streaming**: Logs appear in real-time as tests execute
- **Color Coding**: 
  - 🔵 INFO (blue)
  - 🟢 SUCCESS (green)
  - 🟡 WARNING (yellow)
  - 🔴 ERROR (red)
- **Auto-Scroll**: Logs automatically scroll to latest entry
- **Clear Button**: Clear log display (doesn't delete files)

### Viewing Coverage

- **Circular Meter**: Visual representation of coverage percentage
- **Detailed Stats**: Lines covered, total lines, uncovered lines
- **File Breakdown**: Coverage by file (when available)

### Test History

- **Last 50 Runs**: Sortable table of recent test executions
- **Key Metrics**: Timestamp, passed/failed/errors, pass rate, duration
- **Trend Analysis**: Identify patterns in test results over time

## Architecture

### Backend (Flask)

**File**: `dashboard/app.py`

- **TestRunner Class**: Manages test execution in background threads
- **REST API**: 10 endpoints for test control, results, logs, coverage
- **Server-Sent Events**: Real-time log streaming to frontend
- **In-Memory Storage**: Efficient deque structures for logs and history

**API Endpoints**:
- `GET /` - Dashboard UI
- `GET /api/status` - Current test run status
- `POST /api/tests/run` - Start test execution
- `POST /api/tests/stop` - Stop running tests
- `GET /api/tests/results` - Latest test results
- `GET /api/logs` - Recent logs
- `GET /api/logs/stream` - Live log stream (SSE)
- `GET /api/coverage` - Coverage data
- `GET /api/history` - Test run history
- `GET /api/stats` - Dashboard statistics
- `GET /api/health` - Health check

### Frontend (HTML/CSS/JS)

**File**: `dashboard/templates/index.html`

- **Vanilla JavaScript**: No external dependencies
- **Responsive Design**: Mobile-friendly layout
- **Real-Time Updates**: Auto-refresh every 3 seconds
- **Interactive Tabs**: Logs, results, history sections
- **Progress Visualization**: Circular coverage meter, progress bars

### Logging Infrastructure

**File**: `test_logger.py`

- **Structured Logging**: JSON format for machine parsing
- **Colored Console**: ANSI colors and emojis for readability
- **File Rotation**: Automatic log rotation (10MB main, 5MB errors)
- **Multiple Handlers**: Console, file, JSON, error-only
- **Test Lifecycle**: Methods for test start, end, skip, fail, error
- **Coverage & Performance**: Specialized logging for metrics

**Log Files**:
- `logs/test_suite.log` - Main log (rotating, 10MB, 5 backups)
- `logs/test_suite.json.log` - JSON structured logs
- `logs/errors.log` - Errors only (rotating, 5MB, 3 backups)

## Configuration

### Port Configuration

Default: `5000`

Change in `dashboard/app.py`:
```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
```

### Test Configuration

Modify test execution in `dashboard/app.py`:
```python
# TestRunner.run_tests() method
pytest_args = [
    'pytest',
    test_path,
    '-v',
    '--tb=short',
    '--json-report',
    '--json-report-file=reports/report.json',
    '--cov=ice_pipeline',
    '--cov-report=json:reports/coverage.json'
]
```

### Log Retention

Adjust in `test_logger.py`:
```python
# Number of backup log files
file_handler = RotatingFileHandler(
    'logs/test_suite.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5  # Keep 5 old files
)
```

### History Size

Change in `dashboard/app.py`:
```python
class TestRunner:
    def __init__(self):
        self.test_history = deque(maxlen=50)  # Last 50 runs
        self.log_buffer = deque(maxlen=1000)  # Last 1000 logs
```

## Dependencies

### Python Packages
- `flask==3.1.0` - Web framework
- `flask-cors==5.0.0` - CORS support
- `pytest-json-report==1.5.0` - JSON test reports

Install via:
```bash
pip install -r dashboard/requirements.txt
```

### Existing Test Suite Dependencies
All testing dependencies from main `requirements.txt` are required:
- pytest, pytest-asyncio, pytest-cov, pytest-benchmark
- fastapi, httpx, faker, pandas
- And all other test suite dependencies

## Troubleshooting

### Dashboard Won't Start

**Issue**: `ModuleNotFoundError: No module named 'flask'`

**Solution**:
```bash
source venv/bin/activate
pip install flask flask-cors pytest-json-report
```

### Tests Don't Execute

**Issue**: No tests found or import errors

**Solution**:
```bash
# Ensure in tools directory
cd /home/sebastiangarcia/planmaestro-ecosystem/packages/tools

# Verify pytest works
source venv/bin/activate
pytest tests/ -v
```

### Coverage Not Showing

**Issue**: Coverage meter shows 0%

**Solution**:
```bash
# Run tests with coverage manually first
pytest tests/ --cov=ice_pipeline --cov-report=json:reports/coverage.json

# Refresh dashboard
```

### Logs Not Streaming

**Issue**: Live logs tab is empty

**Solution**:
1. Check browser console for SSE errors
2. Verify Flask server is running
3. Try refreshing the page
4. Check if browser supports Server-Sent Events

### Port Already in Use

**Issue**: `Address already in use: 5000`

**Solution**:
```bash
# Find process using port 5000
lsof -i :5000

# Kill the process
kill -9 <PID>

# Or change port in app.py
```

## File Structure

```
packages/tools/
├── dashboard/
│   ├── app.py              # Flask backend
│   ├── templates/
│   │   └── index.html      # Dashboard UI
│   ├── requirements.txt    # Dashboard dependencies
│   └── README.md          # This file
├── test_logger.py          # Logging infrastructure
├── start_dashboard.sh      # Easy startup script
├── logs/                   # Generated log files
│   ├── test_suite.log
│   ├── test_suite.json.log
│   └── errors.log
├── reports/                # Generated test reports
│   ├── report.json
│   └── coverage.json
└── tests/                  # Test suite
    ├── unit/
    ├── api/
    └── integration/
```

## Integration with Test Suite

The dashboard integrates seamlessly with the existing test suite:

1. **No Code Changes**: Tests run without modification
2. **Logging Integration**: Uses `test_logger.py` for structured logs
3. **Coverage Tools**: Uses existing pytest-cov configuration
4. **Report Formats**: Parses standard JSON reports

## Development

### Adding New Features

1. **Backend**: Add endpoints in `dashboard/app.py`
2. **Frontend**: Modify `dashboard/templates/index.html`
3. **Logging**: Extend methods in `test_logger.py`

### Customizing UI

All styles are in `<style>` section of `index.html`:
- Color scheme: CSS variables at top
- Layout: Flexbox and grid systems
- Animations: CSS transitions and keyframes

### API Extension

Example new endpoint:
```python
@app.route('/api/custom-endpoint', methods=['GET'])
def custom_endpoint():
    return jsonify({
        'status': 'success',
        'data': {}
    })
```

## Best Practices

1. **Run Dashboard Locally**: Not designed for production deployment
2. **Monitor Logs**: Check `logs/` directory for persistent logs
3. **Regular Cleanup**: Old test runs are auto-pruned (50 max)
4. **Browser Support**: Use modern browsers (Chrome, Firefox, Edge)
5. **Single Instance**: Run one dashboard instance at a time

## Security Notes

- **Local Only**: Dashboard is for local development only
- **No Authentication**: No auth required (localhost only)
- **CORS Enabled**: For local frontend development
- **Debug Mode**: Flask runs in debug mode for development

## Performance

- **Lightweight**: Vanilla JS, no heavy frameworks
- **Efficient**: In-memory storage with deque limits
- **Non-Blocking**: Background threads for test execution
- **Real-Time**: SSE streaming for instant updates

## Future Enhancements

Potential improvements (not currently implemented):
- Test filtering by name/category
- Historical trend charts
- Export test reports
- Email notifications
- Multi-user support
- Persistent database storage
- Docker containerization

## Support

For issues or questions:
1. Check this README
2. Review log files in `logs/`
3. Check Flask console output
4. Verify all dependencies installed

## License

Part of the PlanMaestro Ecosystem - Enterprise Tools Platform
