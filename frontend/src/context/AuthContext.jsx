import { useState, useEffect } from 'react';
import { AuthContext } from './AuthContextInstance';
import { authAPI } from '../api/client';

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('adgenie_auth_token'));
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  // Verify and fetch user profile if token exists on application mount
  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem('adgenie_auth_token');
      if (storedToken) {
        try {
          const profile = await authAPI.getMe();
          setUser(profile);
          setToken(storedToken);
        } catch (err) {
          console.warn('Invalid or expired token, clearing session:', err);
          localStorage.removeItem('adgenie_auth_token');
          setToken(null);
          setUser(null);
        }
      }
      setLoading(false);
    };

    initAuth();
  }, []);

  const login = async (email, password) => {
    setAuthError(null);
    try {
      const data = await authAPI.login(email, password);
      const accessToken = data.access_token;
      localStorage.setItem('adgenie_auth_token', accessToken);
      setToken(accessToken);

      // Fetch user profile immediately with the new token
      const profile = await authAPI.getMe();
      setUser(profile);
      return { success: true, user: profile };
    } catch (err) {
      const message =
        err.response?.data?.detail ||
        (err.response?.data?.message) ||
        'Failed to log in. Please check your credentials.';
      setAuthError(message);
      throw new Error(message, { cause: err });
    }
  };

  const register = async (name, email, password) => {
    setAuthError(null);
    try {
      const data = await authAPI.register(name, email, password);
      return { success: true, data };
    } catch (err) {
      let message = 'Registration failed.';
      if (err.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail)) {
          message = err.response.data.detail.map((d) => d.msg || d.message).join(', ');
        } else {
          message = err.response.data.detail;
        }
      }
      setAuthError(message);
      throw new Error(message, { cause: err });
    }
  };

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch (err) {
      console.warn('Logout notification error:', err);
    } finally {
      localStorage.removeItem('adgenie_auth_token');
      setToken(null);
      setUser(null);
      setAuthError(null);
    }
  };

  const value = {
    user,
    token,
    loading,
    authError,
    isAuthenticated: !!user && !!token,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthProvider;
