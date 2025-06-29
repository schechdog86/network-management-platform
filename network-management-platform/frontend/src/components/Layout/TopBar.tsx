import React, { useState } from 'react';
import {
  Toolbar,
  Typography,
  IconButton,
  Badge,
  Menu,
  MenuItem,
  Avatar,
  Box,
  Chip,
  Tooltip,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Notifications as NotificationsIcon,
  AccountCircle,
  ExitToApp,
  Settings,
  WifiTethering,
} from '@mui/icons-material';

import { useAuthStore } from '@/stores/authStore';
import { useWebSocketStatus } from '@/hooks/useWebSocket';

interface TopBarProps {
  onMenuClick: () => void;
}

const TopBar: React.FC<TopBarProps> = ({ onMenuClick }) => {
  const { user, logout } = useAuthStore();
  const { state: wsState, isConnected } = useWebSocketStatus();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    logout();
    handleMenuClose();
  };

  const getConnectionStatusColor = () => {
    switch (wsState) {
      case 'connected':
        return 'success';
      case 'connecting':
        return 'warning';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  const getConnectionStatusText = () => {
    switch (wsState) {
      case 'connected':
        return 'Connected';
      case 'connecting':
        return 'Connecting...';
      case 'error':
        return 'Connection Error';
      default:
        return 'Disconnected';
    }
  };

  return (
    <Toolbar>
      {/* Menu Button */}
      <IconButton
        color="inherit"
        aria-label="open drawer"
        onClick={onMenuClick}
        edge="start"
        sx={{ mr: 2 }}
      >
        <MenuIcon />
      </IconButton>

      {/* Title */}
      <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
        Network Management Platform
      </Typography>

      {/* Connection Status */}
      <Tooltip title={`WebSocket ${getConnectionStatusText()}`}>
        <Chip
          icon={<WifiTethering />}
          label={getConnectionStatusText()}
          color={getConnectionStatusColor() as any}
          variant="outlined"
          size="small"
          sx={{ mr: 2 }}
        />
      </Tooltip>

      {/* Notifications */}
      <IconButton color="inherit" sx={{ mr: 1 }}>
        <Badge badgeContent={0} color="error">
          <NotificationsIcon />
        </Badge>
      </IconButton>

      {/* User Menu */}
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Typography variant="body2" sx={{ mr: 1, display: { xs: 'none', sm: 'block' } }}>
          {user?.username}
        </Typography>
        <IconButton
          color="inherit"
          onClick={handleMenuOpen}
          aria-label="account of current user"
          aria-controls="user-menu"
          aria-haspopup="true"
        >
          <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main' }}>
            {user?.username?.charAt(0).toUpperCase()}
          </Avatar>
        </IconButton>
      </Box>

      {/* User Menu Dropdown */}
      <Menu
        id="user-menu"
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        <MenuItem onClick={handleMenuClose}>
          <Settings sx={{ mr: 1 }} />
          Settings
        </MenuItem>
        <MenuItem onClick={handleLogout}>
          <ExitToApp sx={{ mr: 1 }} />
          Logout
        </MenuItem>
      </Menu>
    </Toolbar>
  );
};

export default TopBar;