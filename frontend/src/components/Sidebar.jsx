import React, { useState } from 'react';
import { Plus, MessageSquare, Trash2, LogOut, Menu, X, Edit3, Check } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import './Sidebar.css';

const Sidebar = ({
    conversations,
    currentThreadId,
    onNewChat,
    onSelectChat,
    onDeleteChat,
    onRenameChat,
}) => {
    const { user, logout } = useAuth();
    const [collapsed, setCollapsed] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [editTitle, setEditTitle] = useState('');

    const startRename = (e, conv) => {
        e.stopPropagation();
        setEditingId(conv.thread_id);
        setEditTitle(conv.title);
    };

    const confirmRename = (e, threadId) => {
        e.stopPropagation();
        if (editTitle.trim()) {
            onRenameChat(threadId, editTitle.trim());
        }
        setEditingId(null);
    };

    const handleDelete = (e, threadId) => {
        e.stopPropagation();
        if (window.confirm('Delete this conversation?')) {
            onDeleteChat(threadId);
        }
    };

    if (collapsed) {
        return (
            <div className="sidebar sidebar-collapsed">
                <button className="sidebar-toggle" onClick={() => setCollapsed(false)}>
                    <Menu size={20} />
                </button>
            </div>
        );
    }

    return (
        <div className="sidebar">
            <div className="sidebar-header">
                <button className="new-chat-btn" onClick={onNewChat}>
                    <Plus size={18} />
                    <span>New Chat</span>
                </button>
                <button className="sidebar-toggle" onClick={() => setCollapsed(true)}>
                    <X size={18} />
                </button>
            </div>

            <div className="sidebar-conversations">
                {conversations.map((conv) => (
                    <div
                        key={conv.thread_id}
                        className={`conv-item ${conv.thread_id === currentThreadId ? 'active' : ''}`}
                        onClick={() => onSelectChat(conv.thread_id)}
                    >
                        <MessageSquare size={16} className="conv-icon" />

                        {editingId === conv.thread_id ? (
                            <input
                                className="conv-rename-input"
                                value={editTitle}
                                onChange={(e) => setEditTitle(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') confirmRename(e, conv.thread_id);
                                    if (e.key === 'Escape') setEditingId(null);
                                }}
                                onClick={(e) => e.stopPropagation()}
                                autoFocus
                            />
                        ) : (
                            <span className="conv-title">{conv.title || 'New Chat'}</span>
                        )}

                        <div className="conv-actions">
                            {editingId === conv.thread_id ? (
                                <button className="conv-action-btn" onClick={(e) => confirmRename(e, conv.thread_id)}>
                                    <Check size={14} />
                                </button>
                            ) : (
                                <button className="conv-action-btn" onClick={(e) => startRename(e, conv)}>
                                    <Edit3 size={14} />
                                </button>
                            )}
                            <button className="conv-action-btn conv-delete" onClick={(e) => handleDelete(e, conv.thread_id)}>
                                <Trash2 size={14} />
                            </button>
                        </div>
                    </div>
                ))}

                {conversations.length === 0 && (
                    <div className="sidebar-empty">No conversations yet</div>
                )}
            </div>

            <div className="sidebar-footer">
                <div className="sidebar-user">
                    <div className="user-avatar">{user?.username?.[0]?.toUpperCase() || '?'}</div>
                    <span className="user-name">{user?.username}</span>
                </div>
                <button className="logout-btn" onClick={logout} title="Logout">
                    <LogOut size={18} />
                </button>
            </div>
        </div>
    );
};

export default Sidebar;
