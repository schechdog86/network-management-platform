import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import { QueryClient, QueryClientProvider } from 'react-query';

// Store imports
import { useAuthStore } from '@/stores/authStore';

// Component imports
import Layout from '@/components/Layout/Layout';
import LoginPage from '@/pages/LoginPage';
import DashboardPage from '@/pages/DashboardPage';
import DevicesPage from '@/pages/DevicesPage';
import NetworkPage from '@/pages/NetworkPage';
import MetricsPage from '@/pages/MetricsPage';
import SettingsPage from '@/pages/SettingsPage';
import PXEBootPage from '@/pages/PXEBootPage';
import ChatPage from '@/pages/ChatPage';
import PredictiveMaintenancePage from '@/pages/PredictiveMaintenancePage';
import LoadingSpinner from '@/components/Common/LoadingSpinner';
import ErrorBoundary from '@/components/Common/ErrorBoundary';
import AsyncErrorBoundary from '@/components/Common/AsyncErrorBoundary';

// Hooks
import { useRealtimeUpdates } from '@/hooks/useWebSocket';

// Create theme
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#121212',
      paper: '#1e1e1e',
    },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          scrollbarColor: '#6b6b6b #2b2b2b',
          '&::-webkit-scrollbar, & *::-webkit-scrollbar': {
            backgroundColor: '#2b2b2b',
          },
          '&::-webkit-scrollbar-thumb, & *::-webkit-scrollbar-thumb': {
            borderRadius: 8,
            backgroundColor: '#6b6b6b',
            minHeight: 24,
            border: '3px solid #2b2b2b',
          },
          '&::-webkit-scrollbar-thumb:focus, & *::-webkit-scrollbar-thumb:focus': {
            backgroundColor: '#959595',
          },
          '&::-webkit-scrollbar-thumb:active, & *::-webkit-scrollbar-thumb:active': {
            backgroundColor: '#959595',
          },
          '&::-webkit-scrollbar-thumb:hover, & *::-webkit-scrollbar-thumb:hover': {
            backgroundColor: '#959595',
          },
          '&::-webkit-scrollbar-corner, & *::-webkit-scrollbar-corner': {
            backgroundColor: '#2b2b2b',
          },
        },
      },
    },
  },
});

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

// Protected Route component
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuthStore();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

// Main App component
const App: React.FC = () => {
  const { isAuthenticated, isLoading, refreshUser } = useAuthStore();

  // Initialize authentication
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token && !isAuthenticated) {
      refreshUser();
    }
  }, [isAuthenticated, refreshUser]);

  if (isLoading) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <LoadingSpinner />
      </ThemeProvider>
    );
  }

  return (
    <ErrorBoundary>
      <AsyncErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <ThemeProvider theme={theme}>
            <CssBaseline />
            <Router>
              <AppContent />
            </Router>
          </ThemeProvider>
        </QueryClientProvider>
      </AsyncErrorBoundary>
    </ErrorBoundary>
  );
};

// App content with routing
const AppContent: React.FC = () => {
  const { isAuthenticated } = useAuthStore();

  // Initialize real-time updates for authenticated users
  if (isAuthenticated) {
    useRealtimeUpdates();
  }

  return (
    <Routes>
      <Route 
        path="/login" 
        element={
          isAuthenticated ? 
            <Navigate to="/dashboard" replace /> : 
            <LoginPage />
        } 
      />
      
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<ErrorBoundary><DashboardPage /></ErrorBoundary>} />
        <Route path="devices" element={<ErrorBoundary><DevicesPage /></ErrorBoundary>} />
        <Route path="network" element={<ErrorBoundary><NetworkPage /></ErrorBoundary>} />
        <Route path="metrics" element={<ErrorBoundary><MetricsPage /></ErrorBoundary>} />
        <Route path="pxe-boot" element={<ErrorBoundary><PXEBootPage /></ErrorBoundary>} />
        <Route path="chat" element={<ErrorBoundary><ChatPage /></ErrorBoundary>} />
        <Route path="predictive-maintenance" element={<ErrorBoundary><PredictiveMaintenancePage /></ErrorBoundary>} />
        <Route path="settings" element={<ErrorBoundary><SettingsPage /></ErrorBoundary>} />
      </Route>
      
      {/* Catch all route */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

export default App;