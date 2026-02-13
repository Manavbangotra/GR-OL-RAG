"""Document processing module for loading and chunking documents"""

from typing import List, Dict, Any
from pathlib import Path
import logging
from datetime import datetime

# Document loaders
from pypdf import PdfReader
from docx import Document as DocxDocument

from app.config import settings

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a chunk of a document"""
    
    def __init__(
        self,
        content: str,
        metadata: Dict[str, Any],
        chunk_id: int
    ):
        self.content = content
        self.metadata = metadata
        self.chunk_id = chunk_id


class DocumentProcessor:
    """Process and chunk documents for RAG"""
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        """Initialize document processor
        
        Args:
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
    
    def load_document(self, file_path: str) -> str:
        """Load document content based on file type
        
        Args:
            file_path: Path to the document
            
        Returns:
            Document content as string
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        try:
            if extension == '.pdf':
                return self._load_pdf(file_path)
            elif extension == '.txt':
                return self._load_txt(file_path)
            elif extension == '.docx':
                return self._load_docx(file_path)
            elif extension == '.md':
                return self._load_txt(file_path)  # Markdown as text
            else:
                raise ValueError(f"Unsupported file type: {extension}")
        except Exception as e:
            logger.error(f"Error loading document {file_path}: {e}")
            raise
    
    def _load_pdf(self, file_path: str) -> str:
        """Load PDF document
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text
        """
        reader = PdfReader(file_path)
        text_parts = []
        
        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text.strip():
                text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    def _load_txt(self, file_path: str) -> str:
        """Load text/markdown document
        
        Args:
            file_path: Path to text file
            
        Returns:
            File content
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _load_docx(self, file_path: str) -> str:
        """Load DOCX document
        
        Args:
            file_path: Path to DOCX file
            
        Returns:
            Extracted text
        """
        doc = DocxDocument(file_path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(paragraphs)
    
    def chunk_text(
        self,
        text: str,
        metadata: Dict[str, Any] = None
    ) -> List[DocumentChunk]:
        """Split text into overlapping chunks
        
        Args:
            text: Text to chunk
            metadata: Metadata to attach to chunks
            
        Returns:
            List of DocumentChunk objects
        """
        if metadata is None:
            metadata = {}
        
        # Simple character-based chunking with overlap
        chunks = []
        start = 0
        chunk_id = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]
            
            # Try to break at sentence boundary if possible
            if end < len(text):
                # Look for sentence endings
                last_period = chunk_text.rfind('.')
                last_newline = chunk_text.rfind('\n')
                break_point = max(last_period, last_newline)
                
                if break_point > self.chunk_size * 0.5:  # At least 50% of chunk size
                    chunk_text = chunk_text[:break_point + 1]
                    end = start + break_point + 1
            
            if chunk_text.strip():
                chunk_metadata = {
                    **metadata,
                    "chunk_id": chunk_id,
                    "start_char": start,
                    "end_char": end
                }
                
                chunks.append(DocumentChunk(
                    content=chunk_text.strip(),
                    metadata=chunk_metadata,
                    chunk_id=chunk_id
                ))
                chunk_id += 1
            
            # Move start position with overlap
            start = end - self.chunk_overlap
            if start >= len(text):
                break
        
        return chunks
    
    def process_document(
        self,
        file_path: str,
        additional_metadata: Dict[str, Any] = None
    ) -> List[DocumentChunk]:
        """Load and chunk a document
        
        Args:
            file_path: Path to document
            additional_metadata: Additional metadata to attach
            
        Returns:
            List of DocumentChunk objects
        """
        path = Path(file_path)
        
        # Load document
        content = self.load_document(file_path)
        
        # Prepare metadata
        metadata = {
            "filename": path.name,
            "file_path": str(path),
            "file_type": path.suffix.lower(),
            "processed_at": datetime.utcnow().isoformat()
        }
        
        if additional_metadata:
            metadata.update(additional_metadata)
        
        # Chunk document
        chunks = self.chunk_text(content, metadata)
        
        logger.info(f"Processed {path.name}: {len(chunks)} chunks created")
        
        return chunks
