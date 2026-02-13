#!/bin/bash

# RAG Chatbot Startup Script

echo "🚀 Starting RAG Chatbot..."

# Detect Python command
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD=python3.11
else
    PYTHON_CMD=python3
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    $PYTHON_CMD -m venv venv || {
        echo "❌ Failed to create venv. Install: sudo apt install python3.11-venv"
        exit 1
    }
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip setuptools wheel -q
pip install -r requirements.txt -q

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Copying from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your configuration before running!"
    exit 1
fi

# Check MongoDB connection
echo "🔍 Checking MongoDB connection..."
python3 -c "from pymongo import MongoClient; import os; from dotenv import load_dotenv; load_dotenv(); client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')); client.admin.command('ping'); print('✓ MongoDB connected')" || {
    echo "❌ MongoDB connection failed. Please ensure MongoDB is running."
    echo "   Install MongoDB: https://www.mongodb.com/docs/manual/installation/"
    echo "   Or use MongoDB Atlas: https://www.mongodb.com/cloud/atlas"
    exit 1
}

# Download embedding model (first time only)
echo "📊 Checking embedding model..."
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" 2>/dev/null || {
    echo "📥 Downloading embedding model (first time only)..."
    python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
}

echo ""
echo "✅ All checks passed!"
echo ""
echo "🌐 Starting FastAPI server..."
echo "   API: http://localhost:8000"
echo "   Docs: http://localhost:8000/docs"
echo ""

# Start the server
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
