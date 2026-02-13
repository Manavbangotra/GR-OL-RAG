# RAG Chatbot with LangGraph

A production-ready RAG (Retrieval-Augmented Generation) chatbot for dropshipping and service points information, built with LangGraph, ChromaDB, FastAPI, and MongoDB.

## 🌟 Features

- 📄 **Document Processing**: Upload PDF, TXT, DOCX, and MD files
- 🔍 **Semantic Search**: ChromaDB vector store with sentence-transformers embeddings
- 🤖 **Dual LLM Support**: Groq API (cloud) and Ollama (local) with automatic fallback
- 🧠 **Conversation Memory**: MongoDB-based checkpointing for persistent conversations
- 🔄 **LangGraph Workflow**: State-based orchestration with LangGraph
- 📊 **Structured Outputs**: JSON responses with confidence scores and source attribution
- 🚀 **FastAPI Backend**: RESTful API with automatic documentation

## 🏗️ Architecture

```
User Query → FastAPI → LangGraph Workflow
                ↓
         1. Process Query
         2. Retrieve Documents (ChromaDB)
         3. Format Context
         4. Generate Answer (Groq/Ollama)
         5. Save State (MongoDB)
                ↓
         Structured Response
```

## 📋 Prerequisites

- Python 3.9+
- MongoDB (local or Atlas)
- Groq API key (for cloud LLM) OR Ollama (for local LLM)

## 🚀 Quick Start

### 1. Clone and Setup

```bash
cd /home/nikhilsharma/Desktop/RAG
chmod +x run.sh
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
nano .env
```

**Required Configuration**:

```env
# MongoDB (choose one)
MONGODB_URI=mongodb://localhost:27017/          # Local MongoDB
# MONGODB_URI=mongodb+srv://user:pass@cluster   # MongoDB Atlas

# LLM Provider (choose one or both)
GROQ_API_KEY=your_groq_api_key_here            # Get from https://console.groq.com
# Or use Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.7b

# Default provider
DEFAULT_LLM_PROVIDER=groq  # or 'ollama'
```

### 3. Install MongoDB

**Option A: Local MongoDB**
```bash
# Ubuntu/Debian
sudo apt-get install -y mongodb

# macOS
brew install mongodb-community

# Start MongoDB
sudo systemctl start mongodb  # Linux
brew services start mongodb-community  # macOS
```

**Option B: MongoDB Atlas (Cloud)**
1. Sign up at https://www.mongodb.com/cloud/atlas
2. Create a free cluster
3. Get connection string and add to `.env`

### 4. Install Ollama (Optional - for local LLM)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull Qwen2.5 model
ollama pull qwen2.5:1.7b

# Verify
ollama list
```

### 5. Run the Application

```bash
./run.sh
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📚 API Endpoints

### Upload Document

```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@dropshipping_guide.pdf"
```

**Response**:
```json
{
  "success": true,
  "message": "Document uploaded and processed successfully",
  "filename": "dropshipping_guide.pdf",
  "chunks_created": 42,
  "document_id": "dropshipping_guide.pdf"
}
```

### Query Chatbot

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the benefits of dropshipping?",
    "thread_id": "user123",
    "llm_provider": "groq",
    "top_k": 5
  }'
```

**Response**:
```json
{
  "query": "What are the benefits of dropshipping?",
  "answer": "Dropshipping offers several key benefits...",
  "confidence": 0.92,
  "sources": [
    {
      "content": "Dropshipping is a business model...",
      "filename": "dropshipping_guide.pdf",
      "page": 3,
      "score": 0.89
    }
  ],
  "thread_id": "user123",
  "timestamp": "2026-01-29T11:07:22.123Z"
}
```

### Get Conversation History

```bash
curl "http://localhost:8000/history/user123"
```

### Health Check

```bash
curl "http://localhost:8000/health"
```

### System Statistics

```bash
curl "http://localhost:8000/stats"
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017/` |
| `GROQ_API_KEY` | Groq API key | - |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model name | `qwen2.5:1.7b` |
| `DEFAULT_LLM_PROVIDER` | Default LLM (`groq` or `ollama`) | `groq` |
| `CHUNK_SIZE` | Document chunk size | `1000` |
| `CHUNK_OVERLAP` | Chunk overlap | `200` |
| `TOP_K_RESULTS` | Number of documents to retrieve | `5` |

### Document Processing

Supported formats:
- **PDF**: `.pdf`
- **Text**: `.txt`
- **Word**: `.docx`
- **Markdown**: `.md`

Max file size: 50MB (configurable via `MAX_UPLOAD_SIZE_MB`)

### LLM Providers

**Groq (Recommended for Production)**:
- Fast cloud inference
- Model: `llama-3.1-70b-versatile`
- Requires API key from https://console.groq.com

**Ollama (Local/Privacy)**:
- Runs locally on your machine
- Model: `qwen2.5:1.7b` (1.7B parameters)
- No API key required
- Lower resource usage

## 🧪 Testing

### Manual Testing

1. **Upload a document**:
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@test_document.pdf"
```

2. **Query without conversation**:
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is dropshipping?"}'
```

3. **Query with conversation memory**:
```bash
# First query
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is dropshipping?", "thread_id": "test123"}'

# Follow-up query (uses context)
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are its advantages?", "thread_id": "test123"}'
```

### Automated Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/ -v
```

## 📊 Project Structure

```
RAG/
├── app/
│   ├── main.py                    # FastAPI application
│   ├── config.py                  # Configuration
│   ├── models/
│   │   └── schemas.py             # Pydantic models
│   ├── services/
│   │   ├── document_processor.py  # Document loading & chunking
│   │   ├── vector_store.py        # ChromaDB operations
│   │   ├── llm_service.py         # Groq/Ollama integration
│   │   └── rag_workflow.py        # LangGraph workflow
│   ├── checkpointer/
│   │   └── mongo_checkpointer.py  # MongoDB checkpointer
│   └── utils/
│       └── embeddings.py          # Embedding generation
├── documents/                     # Uploaded documents
├── chroma_db/                     # ChromaDB storage
├── requirements.txt               # Python dependencies
├── .env                          # Environment variables
├── run.sh                        # Startup script
└── README.md                     # This file
```

## 🔍 How It Works

### 1. Document Upload
- User uploads document via `/upload` endpoint
- Document is processed and split into chunks (1000 chars, 200 overlap)
- Chunks are embedded using `all-MiniLM-L6-v2`
- Embeddings stored in ChromaDB

### 2. Query Processing
- User sends query via `/query` endpoint
- LangGraph workflow executes:
  1. **Process Query**: Clean and prepare query
  2. **Retrieve Documents**: Semantic search in ChromaDB
  3. **Format Context**: Combine retrieved documents
  4. **Generate Answer**: LLM generates structured response
- Response includes answer, confidence, and sources

### 3. Conversation Memory
- Each conversation has a unique `thread_id`
- State is persisted in MongoDB via checkpointer
- Follow-up queries use conversation history
- Enables contextual multi-turn conversations

## 🛠️ Troubleshooting

### MongoDB Connection Error
```bash
# Check if MongoDB is running
sudo systemctl status mongodb  # Linux
brew services list  # macOS

# Start MongoDB
sudo systemctl start mongodb  # Linux
brew services start mongodb-community  # macOS
```

### Groq API Error
- Verify API key in `.env`
- Check rate limits at https://console.groq.com
- Try fallback to Ollama

### Ollama Not Found
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull model
ollama pull qwen2.5:1.7b

# Check if running
ollama list
```

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

## 📈 Performance Tips

1. **Chunk Size**: Adjust `CHUNK_SIZE` based on document type
   - Technical docs: 800-1000
   - Narrative content: 1200-1500

2. **Top-K Results**: Balance between context and speed
   - Fast queries: `top_k=3`
   - Comprehensive answers: `top_k=7`

3. **LLM Selection**:
   - Groq: Faster, better quality, requires internet
   - Ollama: Private, offline, lower resource usage

## 🔐 Security Notes

- **Production**: Set specific CORS origins in `app/main.py`
- **API Keys**: Never commit `.env` to version control
- **MongoDB**: Use authentication in production
- **File Upload**: Implement virus scanning for production

## 📝 License

MIT License - Feel free to use for your projects!

## 🤝 Contributing

Contributions welcome! Please open an issue or PR.

## 📧 Support

For issues or questions, please open a GitHub issue.

---

Built with ❤️ using LangGraph, ChromaDB, FastAPI, and MongoDB
