#!/bin/bash

# Quick Start Script for RAG Chatbot
# This script helps you get started quickly

echo "🚀 RAG Chatbot Quick Start"
echo "=========================="
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Please configure your .env file with:"
    echo "   1. MongoDB connection (MONGODB_URI)"
    echo "   2. Groq API key (GROQ_API_KEY) - Get from https://console.groq.com"
    echo "   OR"
    echo "   3. Install Ollama for local LLM"
    echo ""
    echo "📖 See MONGODB_SETUP.md for MongoDB setup instructions"
    echo ""
    read -p "Press Enter after configuring .env file..."
fi

# Check Python version
echo "🐍 Checking Python version..."
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD=python3.11
elif command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
    # Check if it's at least 3.9
    version=$($PYTHON_CMD --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    if (( $(echo "$version < 3.9" | bc -l) )); then
        echo "❌ Python 3.9+ required. Found: $($PYTHON_CMD --version)"
        echo "   Please install Python 3.11: sudo apt install python3.11 python3.11-venv"
        exit 1
    fi
else
    echo "❌ Python 3 not found. Please install Python 3.11 or higher."
    echo "   Ubuntu/Debian: sudo apt install python3.11 python3.11-venv"
    exit 1
fi

$PYTHON_CMD --version

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    $PYTHON_CMD -m venv venv || {
        echo "❌ Failed to create virtual environment"
        echo "   Install venv: sudo apt install python3.11-venv"
        exit 1
    }
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate || {
    echo "❌ Failed to activate virtual environment"
    exit 1
}

# Install dependencies
echo "📥 Installing dependencies (this may take a few minutes)..."
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Ensure MongoDB is running:"
echo "   - Local: sudo systemctl start mongod"
echo "   - Docker: docker-compose up -d"
echo "   - Atlas: Already running in cloud"
echo ""
echo "2. (Optional) Install Ollama for local LLM:"
echo "   curl -fsSL https://ollama.com/install.sh | sh"
echo "   ollama pull qwen3:1.7b"
echo ""
echo "3. Start the application:"
echo "   ./run.sh"
echo ""
echo "4. Test the API:"
echo "   Open http://localhost:8000/docs in your browser"
echo ""
echo "5. Upload sample documents:"
echo "   curl -X POST http://localhost:8000/upload -F 'file=@sample_documents/dropshipping_guide.md'"
echo ""
echo "6. Try a query:"
echo "   curl -X POST http://localhost:8000/query -H 'Content-Type: application/json' -d '{\"query\": \"What is dropshipping?\"}'"
echo ""
