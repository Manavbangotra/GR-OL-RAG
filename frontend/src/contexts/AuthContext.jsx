import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi } from '../services/api';

const AuthContext = createContext(null);

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // On mount, validate stored token
        const token = localStorage.getItem('access_token');
        if (!token) {
            setLoading(false);
            return;
        }

        authApi
            .getMe()
            .then((data) => setUser(data))
            .catch(() => {
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
            })
            .finally(() => setLoading(false));
    }, []);

    const login = async (username, password) => {
        const data = await authApi.login(username, password);
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        const me = await authApi.getMe();
        setUser(me);
        return me;
    };

    const register = async (username, email, password) => {
        const data = await authApi.register(username, email, password);
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        const me = await authApi.getMe();
        setUser(me);
        return me;
    };

    const logout = () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, register, logout }}>
            {children}
        </AuthContext.Provider>
    );
};
