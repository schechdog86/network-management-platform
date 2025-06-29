import React, { useState, useEffect, ReactNode } from 'react';
import { Alert, AlertTitle, Box, Button, Collapse } from '@mui/material';
import { ExpandMore, ExpandLess } from '@mui/icons-material';

interface AsyncErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, retry: () => void) => ReactNode;
}

interface AsyncError {
  error: Error;
  errorInfo?: string;
}

export const AsyncErrorBoundary: React.FC<AsyncErrorBoundaryProps> = ({ 
  children, 
  fallback 
}) => {
  const [asyncError, setAsyncError] = useState<AsyncError | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      console.error('Unhandled promise rejection:', event.reason);
      
      const error = new Error(
        event.reason?.message || 'An asynchronous error occurred'
      );
      
      setAsyncError({
        error,
        errorInfo: event.reason?.stack || 'No stack trace available',
      });
      
      // Prevent the default browser error handling
      event.preventDefault();
    };

    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, []);

  const handleRetry = () => {
    setAsyncError(null);
    // Force re-render of children
    window.location.reload();
  };

  const handleDismiss = () => {
    setAsyncError(null);
  };

  if (asyncError && fallback) {
    return <>{fallback(asyncError.error, handleRetry)}</>;
  }

  return (
    <>
      {asyncError && (
        <Box sx={{ position: 'fixed', top: 80, right: 20, zIndex: 9999, maxWidth: 500 }}>
          <Alert 
            severity="error" 
            onClose={handleDismiss}
            sx={{ mb: 2 }}
          >
            <AlertTitle>Async Error</AlertTitle>
            {asyncError.error.message}
            
            {process.env.NODE_ENV === 'development' && (
              <Box sx={{ mt: 1 }}>
                <Button
                  size="small"
                  onClick={() => setShowDetails(!showDetails)}
                  startIcon={showDetails ? <ExpandLess /> : <ExpandMore />}
                >
                  {showDetails ? 'Hide' : 'Show'} Details
                </Button>
                
                <Collapse in={showDetails}>
                  <Box
                    sx={{
                      mt: 1,
                      p: 1,
                      bgcolor: 'grey.900',
                      borderRadius: 1,
                      fontSize: '0.75rem',
                      fontFamily: 'monospace',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      maxHeight: 200,
                      overflow: 'auto',
                    }}
                  >
                    {asyncError.errorInfo}
                  </Box>
                </Collapse>
              </Box>
            )}
            
            <Box sx={{ mt: 1 }}>
              <Button size="small" onClick={handleRetry}>
                Retry
              </Button>
            </Box>
          </Alert>
        </Box>
      )}
      {children}
    </>
  );
};

export default AsyncErrorBoundary;