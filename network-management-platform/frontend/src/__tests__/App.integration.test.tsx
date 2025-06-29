import React from 'react';
import { render, screen } from '@testing-library/react';
import App from '../App';
import { useAuthStore } from '@/stores/authStore';
import { useRealtimeUpdates } from '@/hooks/useWebSocket';

// Mock modules
jest.mock('@/stores/authStore');
jest.mock('@/hooks/useWebSocket');

describe('App Integration Tests', () => {
  const mockRefreshUser = jest.fn();
  const mockUseRealtimeUpdates = useRealtimeUpdates as jest.Mock;
  
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseRealtimeUpdates.mockReturnValue(undefined);
    
    // Mock localStorage
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: jest.fn(),
        setItem: jest.fn(),
        removeItem: jest.fn(),
        clear: jest.fn(),
      },
      writable: true,
    });
  });

  describe('Loading State', () => {
    it('should show loading spinner when auth is loading', () => {
      (useAuthStore as unknown as jest.Mock).mockReturnValue({
        isAuthenticated: false,
        isLoading: true,
        refreshUser: mockRefreshUser,
      });

      render(<App />);
      
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  describe('Authentication', () => {
    it('should refresh user when token exists', () => {
      window.localStorage.getItem = jest.fn().mockReturnValue('fake-token');
      
      (useAuthStore as unknown as jest.Mock).mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
        refreshUser: mockRefreshUser,
      });

      render(<App />);
      
      expect(mockRefreshUser).toHaveBeenCalled();
    });

    it('should not refresh user when no token exists', () => {
      window.localStorage.getItem = jest.fn().mockReturnValue(null);
      
      (useAuthStore as unknown as jest.Mock).mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
        refreshUser: mockRefreshUser,
      });

      render(<App />);
      
      expect(mockRefreshUser).not.toHaveBeenCalled();
    });
  });

  describe('Real-time Updates', () => {
    it('should initialize real-time updates when authenticated', () => {
      (useAuthStore as unknown as jest.Mock).mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
        refreshUser: mockRefreshUser,
      });

      render(<App />);
      
      // The hook should be called when the app renders with an authenticated user
      expect(mockUseRealtimeUpdates).toHaveBeenCalled();
    });
  });
});