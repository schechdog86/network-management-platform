import React, { useState, useEffect } from 'react';
import {
  IconButton,
  Badge,
  Popover,
  Box,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemSecondaryAction,
  Button,
  Divider,
  Chip,
  Alert,
  CircularProgress,
  Tabs,
  Tab,
} from '@mui/material';
import {
  Notifications as NotificationsIcon,
  Info as InfoIcon,
  CheckCircle as SuccessIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  GitHub as GitHubIcon,
  DeviceHub as DeviceIcon,
  NetworkCheck as NetworkIcon,
  Security as SecurityIcon,
  Backup as BackupIcon,
  SmartToy as AIIcon,
  Person as UserIcon,
  MarkEmailRead as MarkReadIcon,
  Delete as DeleteIcon,
  DoneAll as DoneAllIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import api from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';

interface Notification {
  id: number;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'critical';
  source: string;
  read: boolean;
  metadata: Record<string, any>;
  created_at: string;
  read_at: string | null;
  user_id: number | null;
}

const NotificationCenter: React.FC = () => {
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [tabValue, setTabValue] = useState(0);
  const [filter, setFilter] = useState<'all' | 'unread'>('all');

  const { lastMessage } = useWebSocket();

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const response = await api.get('/api/v1/notifications/', {
        params: {
          unread_only: filter === 'unread',
          limit: 50,
        },
      });
      setNotifications(response.data);
    } catch (error) {
      console.error('Error fetching notifications:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchUnreadCount = async () => {
    try {
      const response = await api.get('/api/v1/notifications/unread-count');
      setUnreadCount(response.data.unread_count);
    } catch (error) {
      console.error('Error fetching unread count:', error);
    }
  };

  useEffect(() => {
    fetchUnreadCount();
    // Refresh count every minute
    const interval = setInterval(fetchUnreadCount, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (anchorEl) {
      fetchNotifications();
    }
  }, [anchorEl, filter]);

  useEffect(() => {
    // Handle real-time updates
    if (lastMessage) {
      try {
        const data = JSON.parse(lastMessage);
        if (data.type === 'github_event' || data.type === 'notification') {
          // Refresh notifications and count
          fetchUnreadCount();
          if (anchorEl) {
            fetchNotifications();
          }
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    }
  }, [lastMessage]);

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleMarkRead = async (notificationId: number) => {
    try {
      await api.put(`/api/v1/notifications/${notificationId}/read`);
      setNotifications(prevNotifications =>
        prevNotifications.map(n =>
          n.id === notificationId ? { ...n, read: true, read_at: new Date().toISOString() } : n
        )
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (error) {
      console.error('Error marking notification as read:', error);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.put('/api/v1/notifications/mark-all-read');
      setNotifications(prevNotifications =>
        prevNotifications.map(n => ({ ...n, read: true, read_at: new Date().toISOString() }))
      );
      setUnreadCount(0);
    } catch (error) {
      console.error('Error marking all notifications as read:', error);
    }
  };

  const handleDelete = async (notificationId: number) => {
    try {
      await api.delete(`/api/v1/notifications/${notificationId}`);
      setNotifications(prevNotifications =>
        prevNotifications.filter(n => n.id !== notificationId)
      );
      // Update unread count if necessary
      const deletedNotification = notifications.find(n => n.id === notificationId);
      if (deletedNotification && !deletedNotification.read) {
        setUnreadCount(prev => Math.max(0, prev - 1));
      }
    } catch (error) {
      console.error('Error deleting notification:', error);
    }
  };

  const getNotificationIcon = (type: string, source: string) => {
    // Source-specific icons
    const sourceIcons: Record<string, React.ReactElement> = {
      github: <GitHubIcon />,
      device: <DeviceIcon />,
      network: <NetworkIcon />,
      security: <SecurityIcon />,
      backup: <BackupIcon />,
      ai: <AIIcon />,
      user: <UserIcon />,
    };

    if (sourceIcons[source]) {
      return sourceIcons[source];
    }

    // Type-based icons as fallback
    switch (type) {
      case 'success':
        return <SuccessIcon color="success" />;
      case 'warning':
        return <WarningIcon color="warning" />;
      case 'error':
      case 'critical':
        return <ErrorIcon color="error" />;
      default:
        return <InfoIcon color="info" />;
    }
  };

  const getNotificationColor = (type: string): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
    switch (type) {
      case 'success':
        return 'success';
      case 'warning':
        return 'warning';
      case 'error':
      case 'critical':
        return 'error';
      case 'info':
      default:
        return 'info';
    }
  };

  const open = Boolean(anchorEl);
  const id = open ? 'notification-popover' : undefined;

  const filteredNotifications = notifications.filter(n => {
    if (tabValue === 1) return n.source === 'github';
    if (tabValue === 2) return ['device', 'network'].includes(n.source);
    return true;
  });

  return (
    <>
      <IconButton
        aria-describedby={id}
        onClick={handleClick}
        color="inherit"
        sx={{ ml: 2 }}
      >
        <Badge badgeContent={unreadCount} color="error">
          <NotificationsIcon />
        </Badge>
      </IconButton>

      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        PaperProps={{
          sx: { width: 400, maxHeight: 600 }
        }}
      >
        <Box sx={{ p: 2, pb: 1 }}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
            <Typography variant="h6">Notifications</Typography>
            {unreadCount > 0 && (
              <Button
                size="small"
                startIcon={<DoneAllIcon />}
                onClick={handleMarkAllRead}
              >
                Mark all read
              </Button>
            )}
          </Box>

          <Tabs
            value={tabValue}
            onChange={(e, v) => setTabValue(v)}
            variant="fullWidth"
            sx={{ mb: 1 }}
          >
            <Tab label="All" />
            <Tab label="GitHub" />
            <Tab label="System" />
          </Tabs>

          <Box display="flex" gap={1} mb={1}>
            <Chip
              label="All"
              size="small"
              color={filter === 'all' ? 'primary' : 'default'}
              onClick={() => setFilter('all')}
            />
            <Chip
              label="Unread"
              size="small"
              color={filter === 'unread' ? 'primary' : 'default'}
              onClick={() => setFilter('unread')}
            />
          </Box>
        </Box>

        <Divider />

        {loading ? (
          <Box display="flex" justifyContent="center" p={4}>
            <CircularProgress />
          </Box>
        ) : filteredNotifications.length === 0 ? (
          <Box p={4} textAlign="center">
            <Typography color="text.secondary">
              No notifications
            </Typography>
          </Box>
        ) : (
          <List sx={{ maxHeight: 400, overflow: 'auto' }}>
            {filteredNotifications.map((notification) => (
              <ListItem
                key={notification.id}
                sx={{
                  opacity: notification.read ? 0.7 : 1,
                  bgcolor: notification.read ? 'transparent' : 'action.hover',
                }}
              >
                <ListItemIcon>
                  {getNotificationIcon(notification.type, notification.source)}
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Typography variant="body2" fontWeight={notification.read ? 'normal' : 'bold'}>
                      {notification.title}
                    </Typography>
                  }
                  secondary={
                    <Box>
                      <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.875rem' }}>
                        {notification.message}
                      </Typography>
                      <Box display="flex" alignItems="center" gap={1} mt={0.5}>
                        <Chip
                          label={notification.source}
                          size="small"
                          sx={{ height: 20, fontSize: '0.75rem' }}
                        />
                        <Typography variant="caption" color="text.secondary">
                          {format(new Date(notification.created_at), 'MMM d, HH:mm')}
                        </Typography>
                      </Box>
                    </Box>
                  }
                />
                <ListItemSecondaryAction>
                  <Box display="flex" flexDirection="column" gap={0.5}>
                    {!notification.read && (
                      <IconButton
                        size="small"
                        onClick={() => handleMarkRead(notification.id)}
                        title="Mark as read"
                      >
                        <MarkReadIcon fontSize="small" />
                      </IconButton>
                    )}
                    <IconButton
                      size="small"
                      onClick={() => handleDelete(notification.id)}
                      title="Delete"
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Box>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        )}
      </Popover>
    </>
  );
};

export default NotificationCenter;