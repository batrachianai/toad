#!/bin/bash
# Quick setup and test script for Textual TUI Skill

set -e

echo "🚀 Textual TUI Skill - Quick Setup"
echo "=================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    exit 1
fi

echo "✓ Python found: $(python3 --version)"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment exists"
fi

# Activate virtual environment
echo ""
echo "📥 Installing dependencies..."
source venv/bin/activate

# Install dependencies
pip install -q --upgrade pip
pip install -q textual textual-dev psutil

echo "✓ Dependencies installed"
echo ""

# Show available examples
echo "📚 Available examples:"
echo "  1. python examples/todo_app.py        - Todo list application"
echo "  2. python examples/dashboard_app.py   - System monitor dashboard"
echo "  3. python examples/data_viewer.py     - JSON/CSV data viewer"
echo "  4. python examples/worker_demo.py     - Background task patterns"
echo ""
echo "🔥 Run with hot reload:"
echo "  textual run --dev examples/todo_app.py"
echo ""
echo "📦 Build the skill:"
echo "  python scripts/package.py"
echo ""
echo "✅ Setup complete! Activate venv with: source venv/bin/activate"
