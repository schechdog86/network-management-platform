import { Component, ErrorInfo, ReactNode } from 'react';
import { Box, Typography, Button, Paper, Container } from '@mui/material';
import { ErrorOutline, Refresh } from '@mui/icons-material';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorInfo: null,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    
    this.setState({
      errorInfo,
    });

    // Call the optional error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // Here you could also send the error to an error reporting service
    // Example: Sentry.captureException(error, { contexts: { react: errorInfo } });
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render() {
    if (this.state.hasError) {
      // If a custom fallback is provided, use it
      if (this.props.fallback) {
        return <>{this.props.fallback}</>;
      }

      // Default error UI
      return (
        <Container maxWidth="md">
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: '400px',
              py: 4,
            }}
          >
            <Paper
              elevation={3}
              sx={{
                p: 4,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 2,
                width: '100%',
              }}
            >
              <ErrorOutline sx={{ fontSize: 64, color: 'error.main' }} />
              
              <Typography variant="h5" gutterBottom align="center">
                Oops! Something went wrong
              </Typography>
              
              <Typography variant="body1" color="text.secondary" align="center">
                We're sorry for the inconvenience. An unexpected error has occurred.
              </Typography>

              {process.env.NODE_ENV === 'development' && this.state.error && (
                <Box
                  sx={{
                    mt: 2,
                    p: 2,
                    bgcolor: 'grey.900',
                    borderRadius: 1,
                    width: '100%',
                    maxHeight: '300px',
                    overflow: 'auto',
                  }}
                >
                  <Typography
                    variant="caption"
                    component="pre"
                    sx={{
                      fontFamily: 'monospace',
                      color: 'error.light',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {this.state.error.toString()}
                    {this.state.errorInfo && (
                      <>
                        {'\n\nComponent Stack:'}
                        {this.state.errorInfo.componentStack}
                      </>
                    )}
                  </Typography>
                </Box>
              )}

              <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
                <Button
                  variant="contained"
                  startIcon={<Refresh />}
                  onClick={this.handleReset}
                >
                  Try Again
                </Button>
                
                <Button
                  variant="outlined"
                  onClick={() => window.location.href = '/'}
                >
                  Go to Home
                </Button>
              </Box>
            </Paper>
          </Box>
        </Container>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;