import axios from 'axios';

const API_BASE_URL = '/api';

export const api = {
    // Upload document
    uploadDocument: async (file) => {
        const formData = new FormData();
        formData.append('file', file);

        const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },

    // Send query
    sendQuery: async (query, threadId = null, llmProvider = null, topK = 5) => {
        const response = await axios.post(`${API_BASE_URL}/query`, {
            query,
            thread_id: threadId,
            llm_provider: llmProvider,
            top_k: topK,
        });
        return response.data;
    },

    // Get conversation history
    getHistory: async (threadId) => {
        const response = await axios.get(`${API_BASE_URL}/history/${threadId}`);
        return response.data;
    },

    // Delete conversation
    deleteConversation: async (threadId) => {
        const response = await axios.delete(`${API_BASE_URL}/history/${threadId}`);
        return response.data;
    },

    // Health check
    healthCheck: async () => {
        const response = await axios.get(`${API_BASE_URL}/health`);
        return response.data;
    },

    // Get stats
    getStats: async () => {
        const response = await axios.get(`${API_BASE_URL}/stats`);
        return response.data;
    },
};
