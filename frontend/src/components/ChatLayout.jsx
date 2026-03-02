import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './Sidebar';
import ChatInterface from './ChatInterface';
import { api } from '../services/api';
import './ChatLayout.css';

const ChatLayout = () => {
    const [conversations, setConversations] = useState([]);
    const [currentThreadId, setCurrentThreadId] = useState(null);

    const loadConversations = useCallback(async () => {
        try {
            const data = await api.listConversations();
            setConversations(data);
        } catch (err) {
            console.error('Failed to load conversations', err);
        }
    }, []);

    useEffect(() => {
        loadConversations();
    }, [loadConversations]);

    const handleNewChat = () => {
        // Setting threadId to null signals ChatInterface to start fresh
        setCurrentThreadId(null);
    };

    const handleSelectChat = (threadId) => {
        setCurrentThreadId(threadId);
    };

    const handleDeleteChat = async (threadId) => {
        try {
            await api.deleteConversation(threadId);
            setConversations((prev) => prev.filter((c) => c.thread_id !== threadId));
            if (currentThreadId === threadId) {
                setCurrentThreadId(null);
            }
        } catch (err) {
            console.error('Failed to delete conversation', err);
        }
    };

    const handleRenameChat = async (threadId, title) => {
        try {
            await api.renameConversation(threadId, title);
            setConversations((prev) =>
                prev.map((c) => (c.thread_id === threadId ? { ...c, title } : c))
            );
        } catch (err) {
            console.error('Failed to rename conversation', err);
        }
    };

    // Called by ChatInterface when it creates/uses a thread
    const handleThreadCreated = (threadId) => {
        setCurrentThreadId(threadId);
        loadConversations();
    };

    return (
        <div className="chat-layout">
            <Sidebar
                conversations={conversations}
                currentThreadId={currentThreadId}
                onNewChat={handleNewChat}
                onSelectChat={handleSelectChat}
                onDeleteChat={handleDeleteChat}
                onRenameChat={handleRenameChat}
            />
            <ChatInterface
                threadId={currentThreadId}
                onThreadCreated={handleThreadCreated}
            />
        </div>
    );
};

export default ChatLayout;
