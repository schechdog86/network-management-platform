import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@/tests/utils';
import LoginPage from './LoginPage';
import { useAuthStore } from '@/stores/authStore';

// Mock the auth store
jest.mock('@/stores/authStore');

// Mock the Navigate component to prevent navigation during tests
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  Navigate: ({ to }: { to: string }) => <div>Navigate to {to}</div>,
}));

describe('LoginPage', () => {
  const mockLogin = jest.fn();
  const mockClearError = jest.fn();

  const defaultAuthState = {
    login: mockLogin,
    isLoading: false,
    error: null,
    isAuthenticated: false,
    clearError: mockClearError,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (useAuthStore as unknown as jest.Mock).mockReturnValue(defaultAuthState);
  });

  it('renders login form correctly', () => {
    render(<LoginPage />);

    expect(screen.getByRole('heading', { name: 'NetMgmt' })).toBeInTheDocument();
    expect(screen.getByText('Network Management Platform')).toBeInTheDocument();
    expect(screen.getByLabelText('Username')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument();
  });

  it('redirects to dashboard when already authenticated', () => {
    (useAuthStore as unknown as jest.Mock).mockReturnValue({
      ...defaultAuthState,
      isAuthenticated: true,
    });

    render(<LoginPage />);

    expect(screen.getByText('Navigate to /dashboard')).toBeInTheDocument();
  });

  it('displays loading spinner when loading', () => {
    (useAuthStore as unknown as jest.Mock).mockReturnValue({
      ...defaultAuthState,
      isLoading: true,
    });

    render(<LoginPage />);

    expect(screen.getByText('Logging in...')).toBeInTheDocument();
  });

  it('displays error message when error exists', () => {
    const errorMessage = 'Invalid credentials';
    (useAuthStore as unknown as jest.Mock).mockReturnValue({
      ...defaultAuthState,
      error: errorMessage,
    });

    render(<LoginPage />);

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('clears error when typing in input fields', async () => {
    const user = userEvent.setup();
    (useAuthStore as unknown as jest.Mock).mockReturnValue({
      ...defaultAuthState,
      error: 'Some error',
    });

    render(<LoginPage />);

    const usernameInput = screen.getByLabelText('Username');
    await user.type(usernameInput, 'a');

    expect(mockClearError).toHaveBeenCalled();
  });

  it('toggles password visibility', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const passwordInput = screen.getByLabelText('Password');
    const toggleButton = screen.getByLabelText('toggle password visibility');

    expect(passwordInput).toHaveAttribute('type', 'password');

    await user.click(toggleButton);
    expect(passwordInput).toHaveAttribute('type', 'text');

    await user.click(toggleButton);
    expect(passwordInput).toHaveAttribute('type', 'password');
  });

  it('disables submit button when fields are empty', () => {
    render(<LoginPage />);

    const submitButton = screen.getByRole('button', { name: 'Sign In' });
    expect(submitButton).toBeDisabled();
  });

  it('enables submit button when both fields have values', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const usernameInput = screen.getByLabelText('Username');
    const passwordInput = screen.getByLabelText('Password');
    const submitButton = screen.getByRole('button', { name: 'Sign In' });

    await user.type(usernameInput, 'testuser');
    await user.type(passwordInput, 'testpass');

    expect(submitButton).toBeEnabled();
  });

  it('calls login function on form submission', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const usernameInput = screen.getByLabelText('Username');
    const passwordInput = screen.getByLabelText('Password');
    const submitButton = screen.getByRole('button', { name: 'Sign In' });

    await user.type(usernameInput, 'testuser');
    await user.type(passwordInput, 'testpass');
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('testuser', 'testpass');
    });
  });

  it('prevents submission with empty fields', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const submitButton = screen.getByRole('button', { name: 'Sign In' });
    await user.click(submitButton);

    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('trims whitespace from username', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const usernameInput = screen.getByLabelText('Username');
    const passwordInput = screen.getByLabelText('Password');
    const submitButton = screen.getByRole('button', { name: 'Sign In' });

    await user.type(usernameInput, '  testuser  ');
    await user.type(passwordInput, 'testpass');
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('testuser', 'testpass');
    });
  });

  it('disables form inputs when loading', () => {
    (useAuthStore as unknown as jest.Mock).mockReturnValue({
      ...defaultAuthState,
      isLoading: true,
    });

    render(<LoginPage />);

    expect(screen.getByLabelText('Username')).toBeDisabled();
    expect(screen.getByLabelText('Password')).toBeDisabled();
    expect(screen.getByLabelText('toggle password visibility')).toBeDisabled();
  });
});