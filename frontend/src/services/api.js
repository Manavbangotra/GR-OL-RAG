import axios from 'axios';

const API_BASE_URL = '/api';

// Axios instance with auth interceptors
const axiosInstance = axios.create({ baseURL: API_BASE_URL });

// Attach Bearer token to every request
axiosInstance.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Auto-refresh on 401
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
    failedQueue.forEach((prom) => {
        if (error) prom.reject(error);
        else prom.resolve(token);
    });
    failedQueue = [];
};

axiosInstance.interceptors.response.use(
    (res) => res,
    async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
            if (isRefreshing) {
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject });
                }).then((token) => {
                    originalRequest.headers.Authorization = `Bearer ${token}`;
                    return axiosInstance(originalRequest);
                });
            }

            originalRequest._retry = true;
            isRefreshing = true;

            const refreshToken = localStorage.getItem('refresh_token');
            if (!refreshToken) {
                isRefreshing = false;
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
                window.location.href = '/login';
                return Promise.reject(error);
            }

            try {
                const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
                    refresh_token: refreshToken,
                });
                localStorage.setItem('access_token', data.access_token);
                processQueue(null, data.access_token);
                originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
                return axiosInstance(originalRequest);
            } catch (refreshError) {
                processQueue(refreshError, null);
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
                window.location.href = '/login';
                return Promise.reject(refreshError);
            } finally {
                isRefreshing = false;
            }
        }

        return Promise.reject(error);
    }
);

// Auth API (uses plain axios — no auth header needed)
export const authApi = {
    register: async (username, email, password) => {
        const { data } = await axios.post(`${API_BASE_URL}/auth/register`, {
            username,
            email,
            password,
        });
        return data;
    },

    login: async (username, password) => {
        const { data } = await axios.post(`${API_BASE_URL}/auth/login`, {
            username,
            password,
        });
        return data;
    },

    refresh: async (refreshToken) => {
        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
        });
        return data;
    },

    getMe: async () => {
        const { data } = await axiosInstance.get('/auth/me');
        return data;
    },
};

// App API (uses interceptor-equipped axios)
export const api = {
    // Upload document
    uploadDocument: async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        const { data } = await axiosInstance.post('/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return data;
    },

    // Send query (non-streaming fallback)
    sendQuery: async (query, threadId = null, llmProvider = null, topK = 5) => {
        const { data } = await axiosInstance.post('/query', {
            query,
            thread_id: threadId,
            llm_provider: llmProvider,
            top_k: topK,
        });
        return data;
    },

    // Send query with SSE streaming
    // callbacks: { onSources(sources), onToken(token), onDone(threadId), onError(err) }
    sendQueryStream: (query, threadId = null, callbacks = {}, llmProvider = null, topK = 5) => {
        const token = localStorage.getItem('access_token');
        const controller = new AbortController();

        const run = async () => {
            const res = await fetch(`${API_BASE_URL}/query/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({
                    query,
                    thread_id: threadId,
                    llm_provider: llmProvider,
                    top_k: topK,
                }),
                signal: controller.signal,
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || res.statusText);
            }

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // keep incomplete line

                let eventType = null;
                for (const line of lines) {
                    if (line.startsWith('event: ')) {
                        eventType = line.slice(7).trim();
                    } else if (line.startsWith('data: ')) {
                        const raw = line.slice(6);
                        try {
                            const payload = JSON.parse(raw);
                            if (eventType === 'sources' && callbacks.onSources) {
                                callbacks.onSources(payload);
                            } else if (eventType === 'token' && callbacks.onToken) {
                                callbacks.onToken(payload.token);
                            } else if (eventType === 'done' && callbacks.onDone) {
                                callbacks.onDone(payload.thread_id);
                            } else if (eventType === 'error' && callbacks.onError) {
                                callbacks.onError(payload.error);
                            }
                        } catch {
                            // ignore malformed JSON
                        }
                        eventType = null;
                    }
                }
            }
        };

        // Start the stream; return an abort handle
        const promise = run().catch((err) => {
            if (err.name !== 'AbortError' && callbacks.onError) {
                callbacks.onError(err.message);
            }
        });

        return { promise, abort: () => controller.abort() };
    },

    // Get conversation history
    getHistory: async (threadId) => {
        const { data } = await axiosInstance.get(`/history/${threadId}`);
        return data;
    },

    // Delete conversation
    deleteConversation: async (threadId) => {
        const { data } = await axiosInstance.delete(`/history/${threadId}`);
        return data;
    },

    // Conversations
    listConversations: async () => {
        const { data } = await axiosInstance.get('/conversations');
        return data;
    },

    createConversation: async () => {
        const { data } = await axiosInstance.post('/conversations');
        return data;
    },

    renameConversation: async (threadId, title) => {
        const { data } = await axiosInstance.patch(`/conversations/${threadId}`, { title });
        return data;
    },

    // Health check
    healthCheck: async () => {
        const { data } = await axios.get(`${API_BASE_URL}/health`);
        return data;
    },

    // Get stats
    getStats: async () => {
        const { data } = await axiosInstance.get('/stats');
        return data;
    },
};
