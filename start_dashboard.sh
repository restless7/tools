#!/bin/bash

# Testing Suite Dashboard Launcher
# =================================

echo "🧪 Starting Testing Suite Dashboard..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Get script directory
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Creating..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Install dashboard dependencies
echo "📥 Installing dashboard dependencies..."
pip install flask flask-cors pytest-json-report > /dev/null 2>&1

# Ensure required directories exist
mkdir -p logs reports dashboard/templates dashboard/static

# Display information
echo ""
echo "✅ Dashboard starting..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Dashboard URL: http://localhost:5000"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Features:"
echo "  ▶️  Run tests with one click"
echo "  📋  Live test logs streaming"
echo "  📊  Real-time coverage visualization"
echo "  📈  Test results and history"
echo "  🎨  Beautiful, responsive UI"
echo ""
echo "Press Ctrl+C to stop the dashboard"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start the Flask dashboard
export FLASK_APP=dashboard/app.py
export FLASK_ENV=development
python dashboard/app.py
