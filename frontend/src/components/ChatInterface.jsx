import React, { useState, useRef, useEffect } from 'react';
import { Send, Upload, Trash2, FileText, Loader2 } from 'lucide-react';
import { api } from '../services/api';
import './ChatInterface.css';

const ChatInterface = ({ threadId, onThreadCreated }) => {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [streaming, setStreaming] = useState(false);
    const [activeThreadId, setActiveThreadId] = useState(threadId);
    const messagesEndRef = useRef(null);
    const fileInputRef = useRef(null);
    const abortRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // When the parent changes threadId (sidebar click or new chat)
    useEffect(() => {
        setActiveThreadId(threadId);

        if (threadId) {
            api.getHistory(threadId)
                .then((data) => {
                    const loaded = (data.messages || []).map((m) => ({
                        role: m.role,
                        content: m.content,
                        timestamp: m.timestamp,
                    }));
                    setMessages(loaded);
                })
                .catch(() => setMessages([]));
        } else {
            setMessages([]);
        }
    }, [threadId]);

    // Cleanup abort on unmount
    useEffect(() => {
        return () => {
            if (abortRef.current) abortRef.current();
        };
    }, []);

    const handleSend = async () => {
        if (!input.trim() || loading || streaming) return;

        const userMessage = { role: 'user', content: input, timestamp: new Date() };
        setMessages((prev) => [...prev, userMessage]);
        const currentInput = input;
        setInput('');
        setLoading(true);

        try {
            let tid = activeThreadId;

            // If no active thread, create one first
            if (!tid) {
                const { thread_id } = await api.createConversation();
                tid = thread_id;
                setActiveThreadId(tid);
                if (onThreadCreated) onThreadCreated(tid);
            }

            // Add a placeholder assistant message that we'll stream into
            const assistantIdx = messages.length + 1; // +1 for user message we just added
            setMessages((prev) => [
                ...prev,
                { role: 'assistant', content: '', sources: [], timestamp: new Date() },
            ]);
            setLoading(false);
            setStreaming(true);

            const { abort } = api.sendQueryStream(currentInput, tid, {
                onSources: (sources) => {
                    setMessages((prev) => {
                        const updated = [...prev];
                        const last = updated[updated.length - 1];
                        if (last && last.role === 'assistant') {
                            updated[updated.length - 1] = { ...last, sources };
                        }
                        return updated;
                    });
                },
                onToken: (token) => {
                    setMessages((prev) => {
                        const updated = [...prev];
                        const last = updated[updated.length - 1];
                        if (last && last.role === 'assistant') {
                            updated[updated.length - 1] = {
                                ...last,
                                content: last.content + token,
                            };
                        }
                        return updated;
                    });
                },
                onDone: (returnedThreadId) => {
                    setStreaming(false);
                    if (onThreadCreated) onThreadCreated(tid);
                },
                onError: (err) => {
                    setStreaming(false);
                    setMessages((prev) => [
                        ...prev,
                        { role: 'error', content: `Error: ${err}`, timestamp: new Date() },
                    ]);
                },
            });

            abortRef.current = abort;
        } catch (error) {
            setLoading(false);
            setStreaming(false);
            const errorMessage = {
                role: 'error',
                content: `Error: ${error.response?.data?.detail || error.message}`,
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorMessage]);
        }
    };

    const handleFileUpload = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setUploading(true);
        try {
            const response = await api.uploadDocument(file);

            const systemMessage = {
                role: 'system',
                content: `Uploaded "${response.filename}" — processing in background (ID: ${response.upload_id})`,
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, systemMessage]);
        } catch (error) {
            const errorMessage = {
                role: 'error',
                content: `Upload failed: ${error.response?.data?.detail || error.message}`,
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorMessage]);
        } finally {
            setUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const handleClearChat = async () => {
        if (!activeThreadId) return;
        if (window.confirm('Clear this conversation?')) {
            try {
                await api.deleteConversation(activeThreadId);
                setMessages([]);
                setActiveThreadId(null);
                if (onThreadCreated) onThreadCreated(null);
            } catch (error) {
                console.error('Error clearing chat:', error);
            }
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="chat-container">
            <div className="chat-header">
                <div className="header-content">
                    <h1>RAG Chatbot</h1>
                    <p>Dropshipping & Service Points Assistant</p>
                </div>
                <div className="header-actions">
                    <button
                        className="icon-button"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploading}
                        title="Upload Document"
                    >
                        {uploading ? <Loader2 className="spin" size={20} /> : <Upload size={20} />}
                    </button>
                    <button
                        className="icon-button"
                        onClick={handleClearChat}
                        title="Clear Chat"
                    >
                        <Trash2 size={20} />
                    </button>
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,.txt,.docx,.md"
                        onChange={handleFileUpload}
                        style={{ display: 'none' }}
                    />
                </div>
            </div>

            <div className="messages-container">
                {messages.length === 0 && (
                    <div className="empty-state">
                        <FileText size={64} />
                        <h2>Welcome to RAG Chatbot</h2>
                        <p>Upload documents and ask questions about dropshipping and service points</p>
                    </div>
                )}

                {messages.map((msg, idx) => (
                    <div key={idx} className={`message message-${msg.role}`}>
                        <div className="message-content">
                            <div className="message-text">
                                {msg.content}
                                {streaming && idx === messages.length - 1 && msg.role === 'assistant' && (
                                    <span className="cursor-blink">|</span>
                                )}
                            </div>

                            {msg.confidence !== undefined && (
                                <div className="message-meta">
                                    <span className="confidence">
                                        Confidence: {(msg.confidence * 100).toFixed(0)}%
                                    </span>
                                </div>
                            )}

                            {msg.sources && msg.sources.length > 0 && (
                                <div className="sources">
                                    <strong>Sources:</strong>
                                    <ul>
                                        {msg.sources.map((source, i) => (
                                            <li key={i}>
                                                {source.filename} (score: {source.score.toFixed(2)})
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    </div>
                ))}

                {loading && (
                    <div className="message message-assistant">
                        <div className="message-content">
                            <Loader2 className="spin" size={20} />
                            <span>Thinking...</span>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            <div className="input-container">
                <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Ask a question about dropshipping or service points..."
                    disabled={loading || streaming}
                    rows={1}
                />
                <button
                    onClick={handleSend}
                    disabled={!input.trim() || loading || streaming}
                    className="send-button"
                >
                    <Send size={20} />
                </button>
            </div>
        </div>
    );
};

export default ChatInterface;
