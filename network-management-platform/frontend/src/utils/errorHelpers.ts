// Error handling utility functions

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  
  if (typeof error === 'string') {
    return error;
  }
  
  if (error && typeof error === 'object' && 'message' in error) {
    return String(error.message);
  }
  
  if (error && typeof error === 'object' && 'response' in error) {
    const response = (error as any).response;
    if (response?.data?.detail) {
      return String(response.data.detail);
    }
    if (response?.data?.message) {
      return String(response.data.message);
    }
  }
  
  return 'An unknown error occurred';
}

export function isAxiosError(error: unknown): error is { response: { data: { detail?: string; message?: string } } } {
  return (
    error !== null &&
    typeof error === 'object' &&
    'response' in error &&
    error.response !== null &&
    typeof error.response === 'object' &&
    'data' in error.response
  );
}