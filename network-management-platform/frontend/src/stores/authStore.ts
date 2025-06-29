// Authentication store using Zustand

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User } from '@/types';
import { apiService } from '@/services/api';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  clearError: () => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null });
        
        try {
          const tokens = await apiService.login(username, password);
          
          // Store token
          localStorage.setItem('access_token', tokens.access_token);
          
          // Get user info
          const user = await apiService.getCurrentUser();
          
          set({
            user,
            accessToken: tokens.access_token,
            isAuthenticated: true,
            isLoading: false,
            error: null
          });
          
          return true;
        } catch (error) {
          const errorMessage = (error as any)?.response?.data?.detail || 'Login failed';
          set({
            isLoading: false,
            error: errorMessage,
            isAuthenticated: false,
            user: null,
            accessToken: null
          });
          
          localStorage.removeItem('access_token');
          return false;
        }
      },

      logout: () => {
        localStorage.removeItem('access_token');
        set({
          user: null,
          accessToken: null,
          isAuthenticated: false,
          error: null
        });
      },

      refreshUser: async () => {
        const token = localStorage.getItem('access_token');
        if (!token) {
          set({ isAuthenticated: false, user: null, accessToken: null });
          return;
        }

        set({ isLoading: true });
        
        try {
          const user = await apiService.getCurrentUser();
          set({
            user,
            accessToken: token,
            isAuthenticated: true,
            isLoading: false,
            error: null
          });
        } catch (error) {
          console.error('Failed to refresh user:', error);
          // Token might be invalid
          localStorage.removeItem('access_token');
          set({
            user: null,
            accessToken: null,
            isAuthenticated: false,
            isLoading: false,
            error: 'Session expired'
          });
        }
      },

      clearError: () => set({ error: null }),
      
      setLoading: (loading: boolean) => set({ isLoading: loading })
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        isAuthenticated: state.isAuthenticated
      })
    }
  )
);