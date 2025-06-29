import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Divider,
  useTheme,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Devices as DevicesIcon,
  NetworkCheck as NetworkIcon,
  Analytics as MetricsIcon,
  Settings as SettingsIcon,
  DeviceHub as PXEIcon,
  SmartToy as ChatIcon,
  TrendingUp as PredictiveIcon,
} from '@mui/icons-material';

interface SidebarProps {
  onClose?: () => void;
}

const menuItems = [
  {
    text: 'Dashboard',
    path: '/dashboard',
    icon: DashboardIcon,
  },
  {
    text: 'Devices',
    path: '/devices',
    icon: DevicesIcon,
  },
  {
    text: 'Network',
    path: '/network',
    icon: NetworkIcon,
  },
  {
    text: 'Metrics',
    path: '/metrics',
    icon: MetricsIcon,
  },
  {
    text: 'PXE Boot',
    path: '/pxe-boot',
    icon: PXEIcon,
  },
  {
    text: 'AI Assistant',
    path: '/chat',
    icon: ChatIcon,
  },
  {
    text: 'Predictive Maintenance',
    path: '/predictive-maintenance',
    icon: PredictiveIcon,
  },
  {
    text: 'Settings',
    path: '/settings',
    icon: SettingsIcon,
  },
];

const Sidebar: React.FC<SidebarProps> = ({ onClose }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const theme = useTheme();

  const handleItemClick = (path: string) => {
    navigate(path);
    if (onClose) {
      onClose();
    }
  };

  const sidebarContent = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Toolbar
        sx={{
          px: 2,
          bgcolor: theme.palette.primary.main,
          color: theme.palette.primary.contrastText,
        }}
      >
        <NetworkIcon sx={{ mr: 1 }} />
        <Typography variant="h6" noWrap component="div">
          NetMgmt
        </Typography>
      </Toolbar>

      <Divider />

      {/* Navigation Menu */}
      <Box sx={{ flexGrow: 1, overflowY: 'auto' }}>
        <List>
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;

            return (
              <ListItem key={item.text} disablePadding>
                <ListItemButton
                  onClick={() => handleItemClick(item.path)}
                  selected={isActive}
                  sx={{
                    mx: 1,
                    my: 0.5,
                    borderRadius: 1,
                    '&.Mui-selected': {
                      backgroundColor: theme.palette.primary.main,
                      color: theme.palette.primary.contrastText,
                      '&:hover': {
                        backgroundColor: theme.palette.primary.dark,
                      },
                      '& .MuiListItemIcon-root': {
                        color: theme.palette.primary.contrastText,
                      },
                    },
                    '&:hover': {
                      backgroundColor: theme.palette.action.hover,
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      minWidth: 40,
                      color: isActive ? 'inherit' : theme.palette.text.secondary,
                    }}
                  >
                    <Icon />
                  </ListItemIcon>
                  <ListItemText
                    primary={item.text}
                    primaryTypographyProps={{
                      fontSize: '0.9rem',
                      fontWeight: isActive ? 500 : 400,
                    }}
                  />
                </ListItemButton>
              </ListItem>
            );
          })}
        </List>
      </Box>

      <Divider />

      {/* Footer */}
      <Box sx={{ p: 2 }}>
        <Typography
          variant="caption"
          color="text.secondary"
          align="center"
          display="block"
        >
          Network Management Platform
        </Typography>
        <Typography
          variant="caption"
          color="text.secondary"
          align="center"
          display="block"
        >
          v1.0.0
        </Typography>
      </Box>
    </Box>
  );

  return <>{sidebarContent}</>;
};

export default Sidebar;