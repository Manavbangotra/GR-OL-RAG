#!/bin/bash

# Startup script for RAG Chatbot (Backend + Frontend)

echo "🚀 Starting RAG Chatbot System"
echo "================================"
echo ""

# Check if backend venv exists
if [ ! -d "venv" ]; then
    echo "❌ Backend virtual environment not found!"
    echo "   Run: source venv/bin/activate"
    exit 1
fi

# Check if frontend node_modules exists
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

# Start backend in background
echo "🐍 Starting Backend (FastAPI)..."
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 3

# Start frontend
echo "⚛️  Starting Frontend (React)..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Both servers started!"
echo ""
echo "📍 Backend API: http://localhost:8000"
echo "📍 API Docs: http://localhost:8000/docs"
echo "📍 Frontend UI: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for Ctrl+C
trap "echo ''; echo '🛑 Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT

# Keep script running
wait
