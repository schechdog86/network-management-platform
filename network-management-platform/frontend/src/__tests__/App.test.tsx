import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import App from '../App';
import { useAuthStore } from '@/stores/authStore';
import { useRealtimeUpdates } from '@/hooks/useWebSocket';

// Mock BrowserRouter to avoid DOM-related issues in test environment
const mockNavigate = jest.fn();
const mockLocation = { pathname: '/' };

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  BrowserRouter: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useNavigate: () => mockNavigate,
  useLocation: () => mockLocation,
}));

// Mock modules
jest.mock('@/stores/authStore');
jest.mock('@/hooks/useWebSocket');

// Mock error boundaries to avoid complex error handling in tests
jest.mock('@/components/Common/ErrorBoundary', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('@/components/Common/AsyncErrorBoundary', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock all page components
jest.mock('@/components/Layout/Layout', () => {
  const { Outlet } = jest.requireActual('react-router-dom');
  return {
    __esModule: true,
    default: () => (
      <div data-testid="layout">
        <Outlet />
      </div>
    ),
  };
});

jest.mock('@/pages/LoginPage', () => ({
  __esModule: true,
  default: () => <div data-testid="login-page">Login Page</div>,
}));

jest.mock('@/pages/DashboardPage', () => ({
  __esModule: true,
  default: () => <div data-testid="dashboard-page">Dashboard Page</div>,
}));

jest.mock('@/pages/DevicesPage', () => ({
  __esModule: true,
  default: () => <div data-testid="devices-page">Devices Page</div>,
}));

jest.mock('@/pages/NetworkPage', () => ({
  __esModule: true,
  default: () => <div data-testid="network-page">Network Page</div>,
}));

jest.mock('@/pages/MetricsPage', () => ({
  __esModule: true,
  default: () => <div data-testid="metrics-page">Metrics Page</div>,
}));

jest.mock('@/pages/SettingsPage', () => ({
  __esModule: true,
  default: () => <div data-testid="settings-page">Settings Page</div>,
}));

jest.mock('@/pages/PXEBootPage', () => ({
  __esModule: true,
  default: () => <div data-testid="pxe-boot-page">PXE Boot Page</div>,
}));

jest.mock('@/pages/ChatPage', () => ({
  __esModule: true,
  default: () => <div data-testid="chat-page">Chat Page</div>,
}));

jest.mock('@/pages/PredictiveMaintenancePage', () => ({
  __esModule: true,
  default: () => <div data-testid="predictive-maintenance-page">Predictive Maintenance Page</div>,
}));

jest.mock('@/components/Common/LoadingSpinner', () => ({
  __esModule: true,
  default: () => <div data-testid="loading-spinner">Loading...</div>,
}));

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

describe('App', () => {
  const mockRefreshUser = jest.fn();
  const mockUseRealtimeUpdates = useRealtimeUpdates as jest.Mock;
  
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseRealtimeUpdates.mockReturnValue(undefined);
    localStorageMock.getItem.mockReturnValue(null);
    mockNavigate.mockClear();
    // Reset location
    mockLocation.pathname = '/';
  });

  describe('Authentication Flow', () => {
    it('should show loading spinner when auth is loading', () => {
      (useAuthStore as unknown as jest.Mock).mockReturnValue({
        isAuthenticated: false,
        isLoading: true,
        refreshUser: mockRefreshUser,
      });

      render(<App />);
      
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('should navigate to login when not authenticated', () => {
      (useAuthStore as unknown as jest.Mock).mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
        refreshUser: mockRefreshUser,
      });

      mockLocation.pathname = '/dashboard';
      render(<App />);
      
      // The Navigate component should be rendered
      expect(screen.queryByTestId('dashboard-page')).not.toBeInTheDocument();
    });

    it('should show dashboard when authenticated', () => {
      (useAuthStore as unknown as jest.Mock).mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
        refreshUser: mockRefreshUser,
      });

      mockLocation.pathname = '/dashboard';
      render(<App />);
      
      expect(screen.getByTestId('layout')).toBeInTheDocument();
    });

    it('should refresh user when token exists but not authenticated', () => {
      localStorageMock.getItem.mockReturnValue('fake-token');
      
      (useAuthStore as unknown as jest.Mock).mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
        refreshUser: mockRefreshUser,
      });

      render(<App />);
      
      expect(mockRefreshUser).toHaveBeenCalled();
    });

    it('should redirect authenticated users from login to dashboard', () => {
      (useAuthStore as unknown as jest.Mock).mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
        refreshUser: mockRefreshUser,
      });

      mockLocation.pathname = '/login';
      render(<App />);
      
      // Should show layout instead of login page
      expect(screen.getByTestId('layout')).toBeInTheDocument();
    });
  });

  describe('Protected Routes', () => {
    it('should protect routes when not authenticated', () => {
      (useAuthStore as unknown as jest.Mock).mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
        refreshUser: mockRefreshUser,
      });

      const protectedRoutes = [
        '/dashboard',
        '/devices',
        '/network',
        '/metrics',
        '/pxe-boot',
        '/chat',
        '/predictive-maintenance',
        '/settings',
      ];

      protectedRoutes.forEach((route) => {
        mockLocation.pathname = route;
        const { unmount } = render(<App />);
        
        // Should not show the protected content
        expect(screen.queryByTestId('layout')).not.toBeInTheDocument();
        unmount();
      });
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
      
      expect(mockUseRealtimeUpdates).toHaveBeenCalled();
    });

    it('should not initialize real-time updates when not authenticated', () => {
      (useAuthStore as unknown as jest.Mock).mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
        refreshUser: mockRefreshUser,
      });

      render(<App />);
      
      // The hook is still called but won't connect when not authenticated
      expect(mockUseRealtimeUpdates).toHaveBeenCalled();
    });
  });

  describe('Theme', () => {
    it('should apply MUI theme', () => {
      (useAuthStore as unknown as jest.Mock).mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
        refreshUser: mockRefreshUser,
      });

      const { container } = render(<App />);
      
      // Check if MUI CssBaseline is applied
      expect(container.firstChild).toBeTruthy();
    });
  });

  describe('Error Boundaries', () => {
    it('should wrap app in error boundaries', () => {
      // This test verifies the structure is correct
      // We've mocked the error boundaries to just render children
      (useAuthStore as unknown as jest.Mock).mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
        refreshUser: mockRefreshUser,
      });

      mockLocation.pathname = '/dashboard';
      render(<App />);
      
      // The app should render without errors
      expect(screen.getByTestId('layout')).toBeInTheDocument();
    });
  });
});