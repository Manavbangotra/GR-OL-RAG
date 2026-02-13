# RAG Chatbot Frontend

React.js frontend for the RAG chatbot application.

## Features

- 💬 Real-time chat interface
- 📄 Document upload (PDF, TXT, DOCX, MD)
- 🎯 Confidence scores for answers
- 📚 Source attribution
- 🎨 Modern, gradient UI design
- ⚡ Fast and responsive

## Setup

```bash
# Install dependencies
cd frontend
npm install

# Start development server
npm run dev
```

The frontend will run on http://localhost:3000

## Build for Production

```bash
npm run build
npm run preview
```

## API Integration

The frontend connects to the FastAPI backend at `http://localhost:8000` via proxy configuration in `vite.config.js`.

Make sure the backend server is running before starting the frontend.
