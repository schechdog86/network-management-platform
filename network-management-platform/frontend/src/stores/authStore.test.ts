import { act, renderHook } from '@testing-library/react';
import { useAuthStore } from './authStore';
import { apiService } from '@/services/api';

// Mock the API service
jest.mock('@/services/api');

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.localStorage = localStorageMock as any;

describe('authStore', () => {
  const mockUser = {
    id: 1,
    username: 'testuser',
    email: 'test@example.com',
    is_active: true,
    is_admin: false,
    created_at: '2024-01-01T00:00:00Z',
  };

  const mockTokens = {
    access_token: 'mock-access-token',
    token_type: 'bearer',
  };

  beforeEach(() => {
    jest.clearAllMocks();
    localStorageMock.getItem.mockReturnValue(null);
    
    // Reset the store state
    const { result } = renderHook(() => useAuthStore());
    act(() => {
      result.current.logout();
    });
  });

  describe('login', () => {
    it('successfully logs in a user', async () => {
      (apiService.login as jest.Mock).mockResolvedValue(mockTokens);
      (apiService.getCurrentUser as jest.Mock).mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuthStore());

      let loginResult: boolean = false;
      await act(async () => {
        loginResult = await result.current.login('testuser', 'password');
      });

      expect(loginResult).toBe(true);
      expect(result.current.user).toEqual(mockUser);
      expect(result.current.accessToken).toBe(mockTokens.access_token);
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.error).toBeNull();
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'access_token',
        mockTokens.access_token
      );
    });

    it('handles login failure', async () => {
      const errorMessage = 'Invalid credentials';
      (apiService.login as jest.Mock).mockRejectedValue({
        response: { data: { detail: errorMessage } },
      });

      const { result } = renderHook(() => useAuthStore());

      let loginResult: boolean = true;
      await act(async () => {
        loginResult = await result.current.login('testuser', 'wrongpassword');
      });

      expect(loginResult).toBe(false);
      expect(result.current.user).toBeNull();
      expect(result.current.accessToken).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.error).toBe(errorMessage);
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
    });

    it('handles generic login error', async () => {
      (apiService.login as jest.Mock).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useAuthStore());

      let loginResult: boolean = true;
      await act(async () => {
        loginResult = await result.current.login('testuser', 'password');
      });

      expect(loginResult).toBe(false);
      expect(result.current.error).toBe('Login failed');
    });

    it('sets loading state during login', async () => {
      (apiService.login as jest.Mock).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockTokens), 100))
      );
      (apiService.getCurrentUser as jest.Mock).mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuthStore());

      expect(result.current.isLoading).toBe(false);

      const loginPromise = act(async () => {
        await result.current.login('testuser', 'password');
      });

      expect(result.current.isLoading).toBe(true);

      await loginPromise;

      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('logout', () => {
    it('clears user data and removes token', () => {
      const { result } = renderHook(() => useAuthStore());

      // Set initial authenticated state
      act(() => {
        result.current.login('testuser', 'password');
      });

      act(() => {
        result.current.logout();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.accessToken).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.error).toBeNull();
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
    });
  });

  describe('refreshUser', () => {
    it('refreshes user data when token exists', async () => {
      localStorageMock.getItem.mockReturnValue('existing-token');
      (apiService.getCurrentUser as jest.Mock).mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.refreshUser();
      });

      expect(result.current.user).toEqual(mockUser);
      expect(result.current.accessToken).toBe('existing-token');
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.error).toBeNull();
    });

    it('handles refresh failure', async () => {
      localStorageMock.getItem.mockReturnValue('invalid-token');
      (apiService.getCurrentUser as jest.Mock).mockRejectedValue(new Error('Unauthorized'));

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.refreshUser();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.accessToken).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.error).toBe('Session expired');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
    });

    it('does nothing when no token exists', async () => {
      localStorageMock.getItem.mockReturnValue(null);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.refreshUser();
      });

      expect(apiService.getCurrentUser).not.toHaveBeenCalled();
      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('clearError', () => {
    it('clears error message', () => {
      const { result } = renderHook(() => useAuthStore());

      // Set an error
      act(() => {
        result.current.setLoading(true);
      });
      
      // Simulate an error state
      (apiService.login as jest.Mock).mockRejectedValue(new Error('Error'));
      act(async () => {
        await result.current.login('user', 'pass');
      });

      expect(result.current.error).toBeTruthy();

      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('setLoading', () => {
    it('sets loading state', () => {
      const { result } = renderHook(() => useAuthStore());

      expect(result.current.isLoading).toBe(false);

      act(() => {
        result.current.setLoading(true);
      });

      expect(result.current.isLoading).toBe(true);

      act(() => {
        result.current.setLoading(false);
      });

      expect(result.current.isLoading).toBe(false);
    });
  });
});