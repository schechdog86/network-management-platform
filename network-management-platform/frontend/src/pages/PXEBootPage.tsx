import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Button,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Alert,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress,
  FormControlLabel,
  Switch,
  Tabs,
  Tab,
  List,
  ListItem,
  ListItemText,
  // ListItemSecondary, // Not available in MUI
} from '@mui/material';
import {
  PlayArrow as StartIcon,
  Stop as StopIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  Computer as ComputerIcon,
  NetworkCheck as NetworkIcon,
  Storage as StorageIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useWebSocket } from '@/hooks/useWebSocket';
import { api } from '@/services/api';
import LoadingSpinner from '@/components/Common/LoadingSpinner';
import { 
  PXEServerStatus, 
  PXEDeploymentJob, 
  DHCPReservation, 
  DHCPLease,
  PXEServerConfig 
} from '@/types';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`pxe-tabpanel-${index}`}
      aria-labelledby={`pxe-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const PXEBootPage: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [serverStatus, setServerStatus] = useState<PXEServerStatus | null>(null);
  const [deploymentJobs, setDeploymentJobs] = useState<PXEDeploymentJob[]>([]);
  const [reservations, setReservations] = useState<DHCPReservation[]>([]);
  const [leases, setLeases] = useState<DHCPLease[]>([]);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [showDeployDialog, setShowDeployDialog] = useState(false);
  const [showReservationDialog, setShowReservationDialog] = useState(false);
  const [showServerConfigDialog, setShowServerConfigDialog] = useState(false);

  // Form states
  const [deployConfig, setDeployConfig] = useState({
    target_mac: '',
    os_type: 'ubuntu2204',
    hostname: '',
    username: 'admin',
    password: '',
    ssh_keys: '',
    packages: '',
    timezone: 'UTC',
    locale: 'en_US.UTF-8',
    keyboard_layout: 'us',
  });

  const [reservation, setReservation] = useState({
    mac_address: '',
    ip_address: '',
  });

  const [serverConfig, setServerConfig] = useState({
    interface: 'eth0',
    subnet: '192.168.100.0/24',
    tftp_server: '192.168.100.1',
    http_server: 'http://192.168.100.1:8080',
    boot_mode: 'both',
  });

  const { subscribeToChannel, unsubscribeFromChannel } = useWebSocket({
    autoConnect: true,
    onMessage: (message) => {
      if (message.type === 'pxe_boot' && message.data?.type === 'dhcp_lease') {
        loadLeases();
      }
      if (message.type === 'backups' && message.data?.type === 'backup_progress') {
        // Could update deployment status if backing up deployed systems
      }
    }
  });

  useEffect(() => {
    const loadInitialData = async () => {
      setInitialLoading(true);
      try {
        await Promise.all([
          loadServerStatus(),
          loadDeploymentJobs(),
          loadReservations(),
          loadLeases()
        ]);
      } finally {
        setInitialLoading(false);
      }
    };

    loadInitialData();

    // Subscribe to PXE boot events
    subscribeToChannel('pxe_boot');
    subscribeToChannel('backups');

    return () => {
      unsubscribeFromChannel('pxe_boot');
      unsubscribeFromChannel('backups');
    };
  }, [subscribeToChannel, unsubscribeFromChannel]);

  const loadServerStatus = async () => {
    try {
      const response = await api.get('/api/v1/pxe/server/status');
      setServerStatus(response.data);
    } catch (error) {
      console.error('Failed to load server status:', error);
    }
  };

  const loadDeploymentJobs = async () => {
    try {
      const response = await api.get('/api/v1/pxe/deployments');
      setDeploymentJobs(response.data.jobs);
    } catch (error) {
      console.error('Failed to load deployment jobs:', error);
    }
  };

  const loadReservations = async () => {
    try {
      const response = await api.get('/api/v1/pxe/dhcp/reservations');
      setReservations(response.data.reservations);
    } catch (error) {
      console.error('Failed to load reservations:', error);
    }
  };

  const loadLeases = async () => {
    try {
      const response = await api.get('/api/v1/pxe/dhcp/leases');
      setLeases(response.data.leases);
    } catch (error) {
      console.error('Failed to load leases:', error);
    }
  };

  const handleStartServer = async () => {
    setLoading(true);
    try {
      await api.post('/api/v1/pxe/server/start', serverConfig);
      setTimeout(loadServerStatus, 2000); // Check status after 2 seconds
    } catch (error) {
      console.error('Failed to start PXE server:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStopServer = async () => {
    setLoading(true);
    try {
      await api.post('/api/v1/pxe/server/stop');
      await loadServerStatus();
    } catch (error) {
      console.error('Failed to stop PXE server:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateDeployment = async () => {
    setLoading(true);
    try {
      // Process packages and ssh_keys from comma-separated strings to arrays
      const config = {
        ...deployConfig,
        packages: deployConfig.packages.split(',').map(p => p.trim()).filter(p => p),
        ssh_keys: deployConfig.ssh_keys.split('\n').map(k => k.trim()).filter(k => k),
        // Generate password hash (in production, use proper hashing)
        password_hash: deployConfig.password ? 
          `$6$rounds=4096$salt$${btoa(deployConfig.password)}` : undefined,
      };

      await api.post('/api/v1/pxe/deployments', config);
      await loadDeploymentJobs();
      setShowDeployDialog(false);
      
      // Reset form
      setDeployConfig({
        target_mac: '',
        os_type: 'ubuntu2204',
        hostname: '',
        username: 'admin',
        password: '',
        ssh_keys: '',
        packages: '',
        timezone: 'UTC',
        locale: 'en_US.UTF-8',
        keyboard_layout: 'us',
      });
    } catch (error) {
      console.error('Failed to create deployment:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddReservation = async () => {
    setLoading(true);
    try {
      await api.post('/api/v1/pxe/dhcp/reservations', reservation);
      await loadReservations();
      setShowReservationDialog(false);
      setReservation({ mac_address: '', ip_address: '' });
    } catch (error) {
      console.error('Failed to add reservation:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteReservation = async (mac: string) => {
    try {
      await api.delete(`/api/v1/pxe/dhcp/reservations/${mac}`);
      await loadReservations();
    } catch (error) {
      console.error('Failed to delete reservation:', error);
    }
  };

  const isServerRunning = serverStatus?.status === 'running';

  if (initialLoading) {
    return <LoadingSpinner message="Loading PXE Boot Server..." />;
  }

  return (
    <Box>
      {/* Header */}
      <Box mb={3}>
        <Typography variant="h4" component="h1" gutterBottom>
          PXE Boot Server
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Network boot and OS deployment management
        </Typography>
      </Box>

      {/* Server Status Card */}
      <Paper elevation={1} sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} md={4}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <NetworkIcon sx={{ fontSize: 40, color: isServerRunning ? 'success.main' : 'text.disabled' }} />
              <Box>
                <Typography variant="h6">Server Status</Typography>
                <Chip
                  label={serverStatus?.status || 'Unknown'}
                  color={isServerRunning ? 'success' : 'default'}
                  size="small"
                />
              </Box>
            </Box>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Grid container spacing={1}>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">DHCP</Typography>
                <Chip
                  label={serverStatus?.services?.dhcp || 'stopped'}
                  size="small"
                  color={serverStatus?.services?.dhcp === 'running' ? 'success' : 'default'}
                />
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">TFTP</Typography>
                <Chip
                  label={serverStatus?.services?.tftp || 'stopped'}
                  size="small"
                  color={serverStatus?.services?.tftp === 'running' ? 'success' : 'default'}
                />
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">HTTP</Typography>
                <Chip
                  label={serverStatus?.services?.http || 'stopped'}
                  size="small"
                  color={serverStatus?.services?.http === 'running' ? 'success' : 'default'}
                />
              </Grid>
            </Grid>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
              <Button
                variant="outlined"
                startIcon={<SettingsIcon />}
                onClick={() => setShowServerConfigDialog(true)}
                disabled={isServerRunning}
              >
                Configure
              </Button>
              {!isServerRunning ? (
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<StartIcon />}
                  onClick={handleStartServer}
                  disabled={loading}
                >
                  Start Server
                </Button>
              ) : (
                <Button
                  variant="contained"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={handleStopServer}
                  disabled={loading}
                >
                  Stop Server
                </Button>
              )}
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Tabs */}
      <Paper elevation={1}>
        <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
          <Tab label="Deployments" />
          <Tab label="DHCP Reservations" />
          <Tab label="Active Leases" />
        </Tabs>

        {/* Deployments Tab */}
        <TabPanel value={tabValue} index={0}>
          <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between' }}>
            <Typography variant="h6">OS Deployments</Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setShowDeployDialog(true)}
              disabled={!isServerRunning}
            >
              New Deployment
            </Button>
          </Box>

          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Job ID</TableCell>
                  <TableCell>Target MAC</TableCell>
                  <TableCell>OS Type</TableCell>
                  <TableCell>Hostname</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Created</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {deploymentJobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell>{job.id}</TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {job.target_mac}
                      </Typography>
                    </TableCell>
                    <TableCell>{job.os_type}</TableCell>
                    <TableCell>{job.hostname}</TableCell>
                    <TableCell>
                      <Chip
                        label={job.status}
                        size="small"
                        color={job.status === 'completed' ? 'success' : 
                               job.status === 'failed' ? 'error' : 'default'}
                      />
                    </TableCell>
                    <TableCell>
                      {new Date(job.created_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>

        {/* DHCP Reservations Tab */}
        <TabPanel value={tabValue} index={1}>
          <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between' }}>
            <Typography variant="h6">DHCP Reservations</Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setShowReservationDialog(true)}
              disabled={!isServerRunning}
            >
              Add Reservation
            </Button>
          </Box>

          <List>
            {reservations.map((res) => (
              <ListItem
                key={res.mac_address}
                secondaryAction={
                  <IconButton
                    edge="end"
                    onClick={() => handleDeleteReservation(res.mac_address)}
                    disabled={!isServerRunning}
                  >
                    <DeleteIcon />
                  </IconButton>
                }
              >
                <ListItemText
                  primary={res.mac_address}
                  secondary={res.ip_address}
                  primaryTypographyProps={{ fontFamily: 'monospace' }}
                  secondaryTypographyProps={{ fontFamily: 'monospace' }}
                />
              </ListItem>
            ))}
          </List>
        </TabPanel>

        {/* Active Leases Tab */}
        <TabPanel value={tabValue} index={2}>
          <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between' }}>
            <Typography variant="h6">Active DHCP Leases</Typography>
            <IconButton onClick={loadLeases}>
              <RefreshIcon />
            </IconButton>
          </Box>

          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>MAC Address</TableCell>
                  <TableCell>IP Address</TableCell>
                  <TableCell>Lease Time</TableCell>
                  <TableCell>Granted</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {leases.map((lease) => (
                  <TableRow key={lease.mac_address}>
                    <TableCell sx={{ fontFamily: 'monospace' }}>
                      {lease.mac_address}
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'monospace' }}>
                      {lease.ip_address}
                    </TableCell>
                    <TableCell>{lease.lease_time}s</TableCell>
                    <TableCell>
                      {new Date(lease.timestamp).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>
      </Paper>

      {/* Deployment Dialog */}
      <Dialog
        open={showDeployDialog}
        onClose={() => setShowDeployDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Create OS Deployment</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Target MAC Address"
                value={deployConfig.target_mac}
                onChange={(e) => setDeployConfig({ ...deployConfig, target_mac: e.target.value })}
                placeholder="00:11:22:33:44:55"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                select
                label="Operating System"
                value={deployConfig.os_type}
                onChange={(e) => setDeployConfig({ ...deployConfig, os_type: e.target.value })}
              >
                <MenuItem value="ubuntu2204">Ubuntu 22.04 LTS</MenuItem>
                <MenuItem value="ubuntu2404">Ubuntu 24.04 LTS</MenuItem>
                <MenuItem value="debian12">Debian 12</MenuItem>
                <MenuItem value="centos9">CentOS Stream 9</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Hostname"
                value={deployConfig.hostname}
                onChange={(e) => setDeployConfig({ ...deployConfig, hostname: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Username"
                value={deployConfig.username}
                onChange={(e) => setDeployConfig({ ...deployConfig, username: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Password"
                type="password"
                value={deployConfig.password}
                onChange={(e) => setDeployConfig({ ...deployConfig, password: e.target.value })}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={3}
                label="SSH Public Keys"
                value={deployConfig.ssh_keys}
                onChange={(e) => setDeployConfig({ ...deployConfig, ssh_keys: e.target.value })}
                placeholder="Paste SSH public keys (one per line)"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Additional Packages"
                value={deployConfig.packages}
                onChange={(e) => setDeployConfig({ ...deployConfig, packages: e.target.value })}
                placeholder="vim, htop, git (comma-separated)"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Timezone"
                value={deployConfig.timezone}
                onChange={(e) => setDeployConfig({ ...deployConfig, timezone: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Keyboard Layout"
                value={deployConfig.keyboard_layout}
                onChange={(e) => setDeployConfig({ ...deployConfig, keyboard_layout: e.target.value })}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowDeployDialog(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreateDeployment}
            disabled={loading || !deployConfig.target_mac || !deployConfig.hostname}
          >
            Create Deployment
          </Button>
        </DialogActions>
      </Dialog>

      {/* Reservation Dialog */}
      <Dialog
        open={showReservationDialog}
        onClose={() => setShowReservationDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Add DHCP Reservation</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="MAC Address"
                value={reservation.mac_address}
                onChange={(e) => setReservation({ ...reservation, mac_address: e.target.value })}
                placeholder="00:11:22:33:44:55"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="IP Address"
                value={reservation.ip_address}
                onChange={(e) => setReservation({ ...reservation, ip_address: e.target.value })}
                placeholder="192.168.100.50"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowReservationDialog(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleAddReservation}
            disabled={loading || !reservation.mac_address || !reservation.ip_address}
          >
            Add Reservation
          </Button>
        </DialogActions>
      </Dialog>

      {/* Server Configuration Dialog */}
      <Dialog
        open={showServerConfigDialog}
        onClose={() => setShowServerConfigDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>PXE Server Configuration</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Network Interface"
                value={serverConfig.interface}
                onChange={(e) => setServerConfig({ ...serverConfig, interface: e.target.value })}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="DHCP Subnet"
                value={serverConfig.subnet}
                onChange={(e) => setServerConfig({ ...serverConfig, subnet: e.target.value })}
                placeholder="192.168.100.0/24"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="TFTP Server IP"
                value={serverConfig.tftp_server}
                onChange={(e) => setServerConfig({ ...serverConfig, tftp_server: e.target.value })}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="HTTP Server URL"
                value={serverConfig.http_server}
                onChange={(e) => setServerConfig({ ...serverConfig, http_server: e.target.value })}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                select
                label="Boot Mode"
                value={serverConfig.boot_mode}
                onChange={(e) => setServerConfig({ ...serverConfig, boot_mode: e.target.value })}
              >
                <MenuItem value="bios">BIOS Only</MenuItem>
                <MenuItem value="uefi">UEFI Only</MenuItem>
                <MenuItem value="both">Both BIOS & UEFI</MenuItem>
              </TextField>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowServerConfigDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => {
            setShowServerConfigDialog(false);
            // Configuration is saved in state for next server start
          }}>
            Save Configuration
          </Button>
        </DialogActions>
      </Dialog>

      {loading && <LinearProgress sx={{ position: 'fixed', top: 0, left: 0, right: 0 }} />}
    </Box>
  );
};

export default PXEBootPage;