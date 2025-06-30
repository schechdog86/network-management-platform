import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  IconButton,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControlLabel,
  Switch,
  Alert,
  CircularProgress,
  Tooltip,
  Menu,
  MenuItem,
  Grid,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  Divider,
  LinearProgress,
  Snackbar,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Add as AddIcon,
  GetApp as InstallIcon,
  Update as UpdateIcon,
  Delete as RemoveIcon,
  Settings as SettingsIcon,
  Info as InfoIcon,
  PlayArrow as EnableIcon,
  Pause as DisableIcon,
  Undo as RevertIcon,
  Extension as SnapIcon,
  Computer as DeviceIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Schedule as ScheduleIcon,
  CloudDownload as DownloadIcon,
  Security as SecurityIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import api from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';

interface Device {
  id: string;
  hostname: string;
  ip_address: string;
  snapd_enabled: boolean;
  snapd_endpoint?: string;
  snap_config?: any;
}

interface SnapInfo {
  name: string;
  version: string;
  revision: string;
  status: string;
  channel: string;
  installed_size?: number;
  install_date?: string;
  summary?: string;
  description?: string;
  developer?: string;
  tracking_channel?: string;
  refresh_date?: string;
}

interface SnapChange {
  id: string;
  kind: string;
  summary: string;
  status: string;
  ready: boolean;
  spawn_time: string;
  ready_time?: string;
  error?: string;
  tasks: any[];
}

interface SnapdManagerProps {
  device: Device;
  onDeviceUpdate?: (device: Device) => void;
}

const SnapdManager: React.FC<SnapdManagerProps> = ({ device, onDeviceUpdate }) => {
  const [snaps, setSnaps] = useState<SnapInfo[]>([]);
  const [changes, setChanges] = useState<SnapChange[]>([]);
  const [loading, setLoading] = useState(false);
  const [registerDialogOpen, setRegisterDialogOpen] = useState(false);
  const [installDialogOpen, setInstallDialogOpen] = useState(false);
  const [snapDetailsDialogOpen, setSnapDetailsDialogOpen] = useState(false);
  const [selectedSnap, setSelectedSnap] = useState<SnapInfo | null>(null);
  const [actionMenuAnchor, setActionMenuAnchor] = useState<null | HTMLElement>(null);
  const [actionMenuSnap, setActionMenuSnap] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  // Registration form state
  const [endpoint, setEndpoint] = useState(device.snapd_endpoint || '');
  const [authToken, setAuthToken] = useState('');

  // Install form state
  const [installSnapName, setInstallSnapName] = useState('');
  const [installChannel, setInstallChannel] = useState('stable');
  const [installClassic, setInstallClassic] = useState(false);
  const [installDangerous, setInstallDangerous] = useState(false);

  const { lastMessage } = useWebSocket() as { lastMessage: string | null };

  useEffect(() => {
    if (device.snapd_enabled) {
      fetchSnaps();
      fetchChanges();
    }
  }, [device.id, device.snapd_enabled]);

  useEffect(() => {
    // Handle real-time updates
    if (lastMessage) {
      try {
        const data = JSON.parse(lastMessage);
        if (data.device_id === device.id) {
          if (data.type.startsWith('snap_')) {
            // Refresh snaps and changes on snap events
            fetchSnaps();
            fetchChanges();
            
            // Show notification
            if (data.type.endsWith('_completed')) {
              showSnackbar(
                `Snap ${data.type.replace('snap_', '').replace('_completed', '')} completed: ${data.snap_name}`,
                data.success ? 'success' : 'error'
              );
            }
          } else if (data.type === 'snapd_registered') {
            onDeviceUpdate?.({ ...device, snapd_enabled: true });
            fetchSnaps();
          }
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    }
  }, [lastMessage, device.id]);

  const fetchSnaps = async () => {
    if (!device.snapd_enabled) return;
    
    try {
      const response = await api.get(`/api/v1/snapd/devices/${device.id}/snaps`);
      setSnaps(response.data.snaps);
    } catch (error) {
      console.error('Error fetching snaps:', error);
      showSnackbar('Failed to fetch snaps', 'error');
    }
  };

  const fetchChanges = async () => {
    if (!device.snapd_enabled) return;
    
    try {
      const response = await api.get(`/api/v1/snapd/devices/${device.id}/changes`);
      setChanges(response.data.changes);
    } catch (error) {
      console.error('Error fetching changes:', error);
    }
  };

  const handleRegisterDevice = async () => {
    try {
      setLoading(true);
      await api.post(`/api/v1/snapd/devices/${device.id}/register`, {
        endpoint,
        auth_token: authToken || undefined,
      });

      onDeviceUpdate?.({ ...device, snapd_enabled: true, snapd_endpoint: endpoint });
      setRegisterDialogOpen(false);
      showSnackbar('Device registered for snapd management', 'success');
    } catch (error) {
      console.error('Error registering device:', error);
      showSnackbar('Failed to register device', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleUnregisterDevice = async () => {
    if (!window.confirm('Are you sure you want to unregister this device from snapd management?')) {
      return;
    }

    try {
      setLoading(true);
      await api.delete(`/api/v1/snapd/devices/${device.id}/register`);

      onDeviceUpdate?.({ ...device, snapd_enabled: false, snapd_endpoint: undefined });
      setSnaps([]);
      setChanges([]);
      showSnackbar('Device unregistered from snapd management', 'success');
    } catch (error) {
      console.error('Error unregistering device:', error);
      showSnackbar('Failed to unregister device', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleInstallSnap = async () => {
    try {
      setLoading(true);
      await api.post(`/api/v1/snapd/devices/${device.id}/snaps/install`, {
        snap_name: installSnapName,
        channel: installChannel,
        classic: installClassic,
        dangerous: installDangerous,
      });

      setInstallDialogOpen(false);
      setInstallSnapName('');
      setInstallChannel('stable');
      setInstallClassic(false);
      setInstallDangerous(false);
      showSnackbar(`Installing snap: ${installSnapName}`, 'success');
    } catch (error) {
      console.error('Error installing snap:', error);
      showSnackbar('Failed to install snap', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleSnapAction = async (action: string, snapName: string) => {
    try {
      setLoading(true);
      
      switch (action) {
        case 'refresh':
          await api.post(`/api/v1/snapd/devices/${device.id}/snaps/refresh`, {
            snap_name: snapName,
          });
          showSnackbar(`Refreshing snap: ${snapName}`, 'success');
          break;
          
        case 'remove':
          if (window.confirm(`Are you sure you want to remove ${snapName}?`)) {
            await api.post(`/api/v1/snapd/devices/${device.id}/snaps/remove`, {
              snap_name: snapName,
            });
            showSnackbar(`Removing snap: ${snapName}`, 'success');
          }
          break;
          
        case 'revert':
          await api.post(`/api/v1/snapd/devices/${device.id}/snaps/${snapName}/revert`);
          showSnackbar(`Reverting snap: ${snapName}`, 'success');
          break;
          
        case 'enable':
          await api.post(`/api/v1/snapd/devices/${device.id}/snaps/${snapName}/enable`);
          showSnackbar(`Enabling snap: ${snapName}`, 'success');
          break;
          
        case 'disable':
          await api.post(`/api/v1/snapd/devices/${device.id}/snaps/${snapName}/disable`);
          showSnackbar(`Disabling snap: ${snapName}`, 'success');
          break;
      }
      
      setActionMenuAnchor(null);
      setActionMenuSnap(null);
    } catch (error) {
      console.error(`Error performing ${action} on ${snapName}:`, error);
      showSnackbar(`Failed to ${action} snap`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleViewSnapDetails = async (snap: SnapInfo) => {
    try {
      const response = await api.get(`/api/v1/snapd/devices/${device.id}/snaps/${snap.name}`);
      setSelectedSnap(response.data);
      setSnapDetailsDialogOpen(true);
    } catch (error) {
      console.error('Error fetching snap details:', error);
      showSnackbar('Failed to fetch snap details', 'error');
    }
  };

  const showSnackbar = (message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <SuccessIcon color="success" />;
      case 'inactive':
        return <ErrorIcon color="disabled" />;
      case 'broken':
        return <ErrorIcon color="error" />;
      default:
        return <InfoIcon color="info" />;
    }
  };

  const getStatusColor = (status: string): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
    switch (status) {
      case 'active':
        return 'success';
      case 'inactive':
        return 'default';
      case 'broken':
        return 'error';
      default:
        return 'info';
    }
  };

  const getChangeStatusColor = (status: string): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
    switch (status) {
      case 'Done':
        return 'success';
      case 'Error':
        return 'error';
      case 'Doing':
        return 'primary';
      default:
        return 'default';
    }
  };

  const formatSize = (bytes?: number) => {
    if (!bytes) return 'Unknown';
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  if (!device.snapd_enabled) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">
              <SnapIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              Snapd Management
            </Typography>
          </Box>

          <Alert severity="info" sx={{ mb: 2 }}>
            This device is not registered for snapd management. Register it to manage snaps remotely.
          </Alert>

          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setRegisterDialogOpen(true)}
          >
            Register Device
          </Button>

          {/* Registration Dialog */}
          <Dialog open={registerDialogOpen} onClose={() => setRegisterDialogOpen(false)} maxWidth="sm" fullWidth>
            <DialogTitle>Register Device for Snapd Management</DialogTitle>
            <DialogContent>
              <TextField
                fullWidth
                label="Snapd Endpoint"
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder="http://device-ip:port or /run/snapd.socket"
                margin="normal"
                helperText="URL for remote snapd or Unix socket path for local snapd"
              />
              <TextField
                fullWidth
                label="Authentication Token (optional)"
                type="password"
                value={authToken}
                onChange={(e) => setAuthToken(e.target.value)}
                margin="normal"
                helperText="Auth token if required by the snapd instance"
              />
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setRegisterDialogOpen(false)}>Cancel</Button>
              <Button
                onClick={handleRegisterDevice}
                variant="contained"
                disabled={!endpoint.trim() || loading}
              >
                {loading ? <CircularProgress size={20} /> : 'Register'}
              </Button>
            </DialogActions>
          </Dialog>
        </CardContent>
      </Card>
    );
  }

  return (
    <Box>
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">
              <SnapIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              Snapd Management - {device.hostname}
            </Typography>
            <Box>
              <Tooltip title="Refresh">
                <IconButton onClick={() => { fetchSnaps(); fetchChanges(); }} disabled={loading}>
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
              <Button
                variant="contained"
                startIcon={<InstallIcon />}
                onClick={() => setInstallDialogOpen(true)}
                sx={{ ml: 1 }}
                disabled={loading}
              >
                Install Snap
              </Button>
              <Button
                variant="outlined"
                color="error"
                onClick={handleUnregisterDevice}
                sx={{ ml: 1 }}
                disabled={loading}
              >
                Unregister
              </Button>
            </Box>
          </Box>

          {loading && <LinearProgress sx={{ mb: 2 }} />}

          <Grid container spacing={3}>
            {/* Installed Snaps */}
            <Grid item xs={12} md={8}>
              <Typography variant="h6" gutterBottom>
                Installed Snaps ({snaps.length})
              </Typography>
              
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Name</TableCell>
                      <TableCell>Version</TableCell>
                      <TableCell>Channel</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Size</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {snaps.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} align="center">
                          <Typography color="text.secondary" py={2}>
                            No snaps installed
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ) : (
                      snaps.map((snap) => (
                        <TableRow key={snap.name} hover>
                          <TableCell>
                            <Box display="flex" alignItems="center">
                              {getStatusIcon(snap.status)}
                              <Box ml={1}>
                                <Typography variant="body2" fontWeight="medium">
                                  {snap.name}
                                </Typography>
                                {snap.summary && (
                                  <Typography variant="caption" color="text.secondary">
                                    {snap.summary}
                                  </Typography>
                                )}
                              </Box>
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">{snap.version}</Typography>
                            <Typography variant="caption" color="text.secondary">
                              rev {snap.revision}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip label={snap.channel} size="small" />
                          </TableCell>
                          <TableCell>
                            <Chip 
                              label={snap.status} 
                              size="small" 
                              color={getStatusColor(snap.status)}
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {formatSize(snap.installed_size)}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Tooltip title="View Details">
                              <IconButton
                                size="small"
                                onClick={() => handleViewSnapDetails(snap)}
                              >
                                <InfoIcon />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Actions">
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  setActionMenuAnchor(e.currentTarget);
                                  setActionMenuSnap(snap.name);
                                }}
                              >
                                <SettingsIcon />
                              </IconButton>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </Grid>

            {/* Recent Changes */}
            <Grid item xs={12} md={4}>
              <Typography variant="h6" gutterBottom>
                Recent Changes
              </Typography>
              
              <Paper variant="outlined" sx={{ maxHeight: 400, overflow: 'auto' }}>
                <List dense>
                  {changes.length === 0 ? (
                    <ListItem>
                      <ListItemText
                        primary="No recent changes"
                        secondary="Snap operations will appear here"
                      />
                    </ListItem>
                  ) : (
                    changes.slice(0, 10).map((change) => (
                      <ListItem key={change.id}>
                        <ListItemIcon>
                          <ScheduleIcon fontSize="small" />
                        </ListItemIcon>
                        <ListItemText
                          primary={change.summary}
                          secondary={
                            <Box>
                              <Typography variant="caption" component="div">
                                {format(new Date(change.spawn_time), 'MMM d, HH:mm')}
                              </Typography>
                              <Chip
                                label={change.status}
                                size="small"
                                color={getChangeStatusColor(change.status)}
                                sx={{ mt: 0.5 }}
                              />
                            </Box>
                          }
                        />
                      </ListItem>
                    ))
                  )}
                </List>
              </Paper>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Action Menu */}
      <Menu
        anchorEl={actionMenuAnchor}
        open={Boolean(actionMenuAnchor)}
        onClose={() => {
          setActionMenuAnchor(null);
          setActionMenuSnap(null);
        }}
      >
        <MenuItem onClick={() => handleSnapAction('refresh', actionMenuSnap!)}>
          <UpdateIcon sx={{ mr: 1 }} fontSize="small" />
          Refresh
        </MenuItem>
        <MenuItem onClick={() => handleSnapAction('revert', actionMenuSnap!)}>
          <RevertIcon sx={{ mr: 1 }} fontSize="small" />
          Revert
        </MenuItem>
        <Divider />
        <MenuItem onClick={() => handleSnapAction('enable', actionMenuSnap!)}>
          <EnableIcon sx={{ mr: 1 }} fontSize="small" />
          Enable
        </MenuItem>
        <MenuItem onClick={() => handleSnapAction('disable', actionMenuSnap!)}>
          <DisableIcon sx={{ mr: 1 }} fontSize="small" />
          Disable
        </MenuItem>
        <Divider />
        <MenuItem 
          onClick={() => handleSnapAction('remove', actionMenuSnap!)}
          sx={{ color: 'error.main' }}
        >
          <RemoveIcon sx={{ mr: 1 }} fontSize="small" />
          Remove
        </MenuItem>
      </Menu>

      {/* Install Snap Dialog */}
      <Dialog open={installDialogOpen} onClose={() => setInstallDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Install Snap</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Snap Name"
            value={installSnapName}
            onChange={(e) => setInstallSnapName(e.target.value)}
            margin="normal"
            placeholder="e.g., firefox, code, docker"
          />
          <TextField
            fullWidth
            label="Channel"
            value={installChannel}
            onChange={(e) => setInstallChannel(e.target.value)}
            margin="normal"
            placeholder="stable, candidate, beta, edge"
          />
          <FormControlLabel
            control={
              <Switch
                checked={installClassic}
                onChange={(e) => setInstallClassic(e.target.checked)}
              />
            }
            label="Classic confinement"
          />
          <FormControlLabel
            control={
              <Switch
                checked={installDangerous}
                onChange={(e) => setInstallDangerous(e.target.checked)}
              />
            }
            label="Allow unsigned snap"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setInstallDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleInstallSnap}
            variant="contained"
            disabled={!installSnapName.trim() || loading}
          >
            Install
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snap Details Dialog */}
      <Dialog 
        open={snapDetailsDialogOpen} 
        onClose={() => setSnapDetailsDialogOpen(false)} 
        maxWidth="md" 
        fullWidth
      >
        <DialogTitle>
          Snap Details: {selectedSnap?.name}
        </DialogTitle>
        <DialogContent>
          {selectedSnap && (
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <Typography variant="subtitle2" gutterBottom>Version</Typography>
                <Typography variant="body2" gutterBottom>{selectedSnap.version}</Typography>
                
                <Typography variant="subtitle2" gutterBottom>Revision</Typography>
                <Typography variant="body2" gutterBottom>{selectedSnap.revision}</Typography>
                
                <Typography variant="subtitle2" gutterBottom>Channel</Typography>
                <Typography variant="body2" gutterBottom>{selectedSnap.channel}</Typography>
                
                <Typography variant="subtitle2" gutterBottom>Status</Typography>
                <Chip label={selectedSnap.status} color={getStatusColor(selectedSnap.status)} />
              </Grid>
              
              <Grid item xs={12} sm={6}>
                <Typography variant="subtitle2" gutterBottom>Size</Typography>
                <Typography variant="body2" gutterBottom>{formatSize(selectedSnap.installed_size)}</Typography>
                
                <Typography variant="subtitle2" gutterBottom>Developer</Typography>
                <Typography variant="body2" gutterBottom>{selectedSnap.developer || 'Unknown'}</Typography>
                
                <Typography variant="subtitle2" gutterBottom>Install Date</Typography>
                <Typography variant="body2" gutterBottom>
                  {selectedSnap.install_date ? format(new Date(selectedSnap.install_date), 'PPp') : 'Unknown'}
                </Typography>
                
                <Typography variant="subtitle2" gutterBottom>Last Refresh</Typography>
                <Typography variant="body2" gutterBottom>
                  {selectedSnap.refresh_date ? format(new Date(selectedSnap.refresh_date), 'PPp') : 'Never'}
                </Typography>
              </Grid>
              
              {selectedSnap.description && (
                <Grid item xs={12}>
                  <Typography variant="subtitle2" gutterBottom>Description</Typography>
                  <Typography variant="body2">{selectedSnap.description}</Typography>
                </Grid>
              )}
            </Grid>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSnapDetailsDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        message={snackbar.message}
      />
    </Box>
  );
};

export default SnapdManager;