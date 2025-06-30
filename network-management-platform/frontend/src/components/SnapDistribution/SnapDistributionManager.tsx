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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  Alert,
  CircularProgress,
  LinearProgress,
  Tooltip,
  Grid,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Snackbar,
  Divider,
  Tab,
  Tabs,
  TabPanel,
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  Undo as RollbackIcon,
  Timeline as TimelineIcon,
  CloudDownload as DistributeIcon,
  Settings as ConfigIcon,
  Info as InfoIcon,
  Warning as WarningIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  ExpandMore as ExpandMoreIcon,
  Visibility as ViewIcon,
  Schedule as ScheduleIcon,
  Storage as StoreIcon,
  Security as SecurityIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import api from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';

interface SnapDistribution {
  distribution_id: string;
  snap_name: string;
  current_phase: number;
  total_phases: number;
  devices_targeted: number;
  devices_updated: number;
  devices_failed: number;
  progress_percent: number;
  status: string;
  phase_start_time: string;
  next_phase_time?: string;
  errors: string[];
  health_metrics: Record<string, any>;
}

interface StoreProxy {
  proxy_id: string;
  endpoint: string;
  registered_at: string;
  cached_snaps: number;
}

interface Device {
  id: string;
  hostname: string;
  ip_address: string;
  snapd_enabled: boolean;
}

const SnapDistributionManager: React.FC = () => {
  const [distributions, setDistributions] = useState<SnapDistribution[]>([]);
  const [storeProxies, setStoreProxies] = useState<StoreProxy[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(false);
  const [tabValue, setTabValue] = useState(0);
  
  // Dialog states
  const [createDistDialogOpen, setCreateDistDialogOpen] = useState(false);
  const [proxyDialogOpen, setProxyDialogOpen] = useState(false);
  const [logsDialogOpen, setLogsDialogOpen] = useState(false);
  const [selectedDistribution, setSelectedDistribution] = useState<SnapDistribution | null>(null);
  
  // Form states
  const [snapName, setSnapName] = useState('');
  const [sourceChannel, setSourceChannel] = useState({
    track: 'latest',
    risk: 'stable',
    branch: ''
  });
  const [targetChannel, setTargetChannel] = useState({
    track: 'latest',
    risk: 'stable',
    branch: ''
  });
  const [selectedDevices, setSelectedDevices] = useState<string[]>([]);
  const [rolloutStrategy, setRolloutStrategy] = useState('progressive');
  const [rolloutPhases, setRolloutPhases] = useState([10, 30, 70, 100]);
  const [phaseDuration, setPhaseDuration] = useState(24);
  const [rollbackThreshold, setRollbackThreshold] = useState(5.0);
  const [healthCheckEnabled, setHealthCheckEnabled] = useState(true);
  const [approvalRequired, setApprovalRequired] = useState(false);
  
  // Proxy form states
  const [proxyId, setProxyId] = useState('');
  const [proxyEndpoint, setProxyEndpoint] = useState('');
  const [proxyAuthToken, setProxyAuthToken] = useState('');
  
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error' | 'warning' | 'info';
  }>({
    open: false,
    message: '',
    severity: 'success',
  });

  const { lastMessage } = useWebSocket() as { lastMessage: string | null };

  useEffect(() => {
    fetchDistributions();
    fetchStoreProxies();
    fetchDevices();
  }, []);

  useEffect(() => {
    // Handle real-time updates
    if (lastMessage) {
      try {
        const data = JSON.parse(lastMessage);
        if (data.type?.startsWith('snap_distribution_')) {
          fetchDistributions();
          
          if (data.type === 'snap_distribution_created') {
            showSnackbar('New snap distribution created', 'success');
          } else if (data.type === 'snap_distribution_completed') {
            showSnackbar(`Distribution completed: ${data.snap_name}`, 'success');
          } else if (data.type === 'snap_distribution_failed') {
            showSnackbar(`Distribution failed: ${data.snap_name}`, 'error');
          }
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    }
  }, [lastMessage]);

  const fetchDistributions = async () => {
    try {
      const response = await api.get('/api/v1/snap-distribution/distributions');
      setDistributions(response.data);
    } catch (error) {
      console.error('Error fetching distributions:', error);
      showSnackbar('Failed to fetch distributions', 'error');
    }
  };

  const fetchStoreProxies = async () => {
    try {
      const response = await api.get('/api/v1/snap-distribution/store-proxy/list');
      setStoreProxies(response.data.proxies);
    } catch (error) {
      console.error('Error fetching store proxies:', error);
    }
  };

  const fetchDevices = async () => {
    try {
      const response = await api.get('/api/v1/devices');
      // Filter for snapd-enabled devices
      const snapdDevices = response.data.filter((device: Device) => device.snapd_enabled);
      setDevices(snapdDevices);
    } catch (error) {
      console.error('Error fetching devices:', error);
    }
  };

  const handleCreateDistribution = async () => {
    try {
      setLoading(true);
      
      const distributionRequest = {
        snap_name: snapName,
        source_channel: sourceChannel,
        target_channel: targetChannel,
        target_devices: selectedDevices,
        rollout_policy: {
          strategy: rolloutStrategy,
          phases: rolloutPhases,
          phase_duration_hours: phaseDuration,
          rollback_threshold_percent: rollbackThreshold,
          health_check_enabled: healthCheckEnabled,
          approval_required: approvalRequired
        },
        metadata: {
          created_via: 'web_ui'
        }
      };

      await api.post('/api/v1/snap-distribution/distributions', distributionRequest);
      
      setCreateDistDialogOpen(false);
      resetCreateForm();
      fetchDistributions();
      showSnackbar('Distribution created successfully', 'success');
      
    } catch (error) {
      console.error('Error creating distribution:', error);
      showSnackbar('Failed to create distribution', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterProxy = async () => {
    try {
      setLoading(true);
      
      await api.post('/api/v1/snap-distribution/store-proxy/register', {
        proxy_id: proxyId,
        endpoint: proxyEndpoint,
        auth_token: proxyAuthToken || undefined
      });
      
      setProxyDialogOpen(false);
      resetProxyForm();
      fetchStoreProxies();
      showSnackbar('Store proxy registered successfully', 'success');
      
    } catch (error) {
      console.error('Error registering proxy:', error);
      showSnackbar('Failed to register store proxy', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDistributionAction = async (action: string, distributionId: string) => {
    try {
      setLoading(true);
      
      await api.post(`/api/v1/snap-distribution/distributions/${distributionId}/${action}`);
      
      fetchDistributions();
      showSnackbar(`Distribution ${action} successful`, 'success');
      
    } catch (error) {
      console.error(`Error ${action} distribution:`, error);
      showSnackbar(`Failed to ${action} distribution`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const resetCreateForm = () => {
    setSnapName('');
    setSourceChannel({ track: 'latest', risk: 'stable', branch: '' });
    setTargetChannel({ track: 'latest', risk: 'stable', branch: '' });
    setSelectedDevices([]);
    setRolloutStrategy('progressive');
    setRolloutPhases([10, 30, 70, 100]);
    setPhaseDuration(24);
    setRollbackThreshold(5.0);
    setHealthCheckEnabled(true);
    setApprovalRequired(false);
  };

  const resetProxyForm = () => {
    setProxyId('');
    setProxyEndpoint('');
    setProxyAuthToken('');
  };

  const showSnackbar = (message: string, severity: 'success' | 'error' | 'warning' | 'info') => {
    setSnackbar({ open: true, message, severity });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <SuccessIcon color="success" />;
      case 'failed':
      case 'rollback_failed':
        return <ErrorIcon color="error" />;
      case 'active':
      case 'rolling_back':
        return <CircularProgress size={20} />;
      case 'paused':
        return <PauseIcon color="warning" />;
      default:
        return <InfoIcon color="info" />;
    }
  };

  const getStatusColor = (status: string): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'failed':
      case 'rollback_failed':
        return 'error';
      case 'active':
      case 'rolling_back':
        return 'primary';
      case 'paused':
        return 'warning';
      default:
        return 'default';
    }
  };

  const renderDistributionsTab = () => (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">
          <DistributeIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          Snap Distributions ({distributions.length})
        </Typography>
        <Box>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchDistributions} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setCreateDistDialogOpen(true)}
            sx={{ ml: 1 }}
            disabled={loading}
          >
            Create Distribution
          </Button>
        </Box>
      </Box>

      {loading && <LinearProgress sx={{ mb: 2 }} />}

      <TableContainer component={Paper} variant="outlined">
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Snap Name</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Progress</TableCell>
              <TableCell>Phase</TableCell>
              <TableCell>Devices</TableCell>
              <TableCell>Created</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {distributions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <Typography color="text.secondary" py={2}>
                    No distributions found
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              distributions.map((dist) => (
                <TableRow key={dist.distribution_id} hover>
                  <TableCell>
                    <Box display="flex" alignItems="center">
                      {getStatusIcon(dist.status)}
                      <Box ml={1}>
                        <Typography variant="body2" fontWeight="medium">
                          {dist.snap_name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          ID: {dist.distribution_id.substring(0, 8)}...
                        </Typography>
                      </Box>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Chip 
                      label={dist.status} 
                      size="small" 
                      color={getStatusColor(dist.status)}
                    />
                  </TableCell>
                  <TableCell>
                    <Box width="100px">
                      <LinearProgress 
                        variant="determinate" 
                        value={dist.progress_percent} 
                        sx={{ mb: 0.5 }}
                      />
                      <Typography variant="caption">
                        {dist.progress_percent.toFixed(1)}%
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {dist.current_phase + 1} / {dist.total_phases}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {dist.devices_updated} / {dist.devices_targeted}
                    </Typography>
                    {dist.devices_failed > 0 && (
                      <Typography variant="caption" color="error">
                        {dist.devices_failed} failed
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {format(new Date(dist.phase_start_time), 'MMM d, HH:mm')}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="View Details">
                      <IconButton
                        size="small"
                        onClick={() => {
                          setSelectedDistribution(dist);
                          setLogsDialogOpen(true);
                        }}
                      >
                        <ViewIcon />
                      </IconButton>
                    </Tooltip>
                    
                    {dist.status === 'active' && (
                      <Tooltip title="Pause">
                        <IconButton
                          size="small"
                          onClick={() => handleDistributionAction('pause', dist.distribution_id)}
                        >
                          <PauseIcon />
                        </IconButton>
                      </Tooltip>
                    )}
                    
                    {dist.status === 'paused' && (
                      <Tooltip title="Resume">
                        <IconButton
                          size="small"
                          onClick={() => handleDistributionAction('resume', dist.distribution_id)}
                        >
                          <PlayIcon />
                        </IconButton>
                      </Tooltip>
                    )}
                    
                    {['active', 'paused'].includes(dist.status) && (
                      <Tooltip title="Rollback">
                        <IconButton
                          size="small"
                          onClick={() => handleDistributionAction('rollback', dist.distribution_id)}
                        >
                          <RollbackIcon />
                        </IconButton>
                      </Tooltip>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );

  const renderStoreProxiesTab = () => (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">
          <StoreIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          Store Proxies ({storeProxies.length})
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setProxyDialogOpen(true)}
          disabled={loading}
        >
          Register Proxy
        </Button>
      </Box>

      <Grid container spacing={2}>
        {storeProxies.length === 0 ? (
          <Grid item xs={12}>
            <Alert severity="info">
              No store proxies registered. Register a snap store proxy to enable caching and distribution control.
            </Alert>
          </Grid>
        ) : (
          storeProxies.map((proxy) => (
            <Grid item xs={12} md={6} key={proxy.proxy_id}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    {proxy.proxy_id}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    {proxy.endpoint}
                  </Typography>
                  <Typography variant="caption" display="block">
                    Registered: {format(new Date(proxy.registered_at), 'PPp')}
                  </Typography>
                  <Typography variant="caption" display="block">
                    Cached Snaps: {proxy.cached_snaps}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))
        )}
      </Grid>
    </Box>
  );

  return (
    <Box>
      <Card>
        <CardContent>
          <Typography variant="h5" gutterBottom>
            <SecurityIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            Snap Distribution Management
          </Typography>
          
          <Tabs value={tabValue} onChange={(e, newValue) => setTabValue(newValue)} sx={{ mb: 2 }}>
            <Tab label="Distributions" />
            <Tab label="Store Proxies" />
          </Tabs>

          {tabValue === 0 && renderDistributionsTab()}
          {tabValue === 1 && renderStoreProxiesTab()}
        </CardContent>
      </Card>

      {/* Create Distribution Dialog */}
      <Dialog open={createDistDialogOpen} onClose={() => setCreateDistDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Create Snap Distribution</DialogTitle>
        <DialogContent>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Snap Name"
                value={snapName}
                onChange={(e) => setSnapName(e.target.value)}
                margin="normal"
                placeholder="e.g., firefox, code, docker"
              />
            </Grid>
            
            <Grid item xs={6}>
              <Typography variant="subtitle2" gutterBottom>Source Channel</Typography>
              <FormControl fullWidth margin="normal">
                <InputLabel>Risk</InputLabel>
                <Select
                  value={sourceChannel.risk}
                  onChange={(e) => setSourceChannel({...sourceChannel, risk: e.target.value})}
                >
                  <MenuItem value="stable">Stable</MenuItem>
                  <MenuItem value="candidate">Candidate</MenuItem>
                  <MenuItem value="beta">Beta</MenuItem>
                  <MenuItem value="edge">Edge</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={6}>
              <Typography variant="subtitle2" gutterBottom>Target Channel</Typography>
              <FormControl fullWidth margin="normal">
                <InputLabel>Risk</InputLabel>
                <Select
                  value={targetChannel.risk}
                  onChange={(e) => setTargetChannel({...targetChannel, risk: e.target.value})}
                >
                  <MenuItem value="stable">Stable</MenuItem>
                  <MenuItem value="candidate">Candidate</MenuItem>
                  <MenuItem value="beta">Beta</MenuItem>
                  <MenuItem value="edge">Edge</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12}>
              <FormControl fullWidth margin="normal">
                <InputLabel>Target Devices</InputLabel>
                <Select
                  multiple
                  value={selectedDevices}
                  onChange={(e) => setSelectedDevices(e.target.value as string[])}
                  renderValue={(selected) => `${selected.length} devices selected`}
                >
                  {devices.map((device) => (
                    <MenuItem key={device.id} value={device.id}>
                      {device.hostname} ({device.ip_address})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12}>
              <FormControl fullWidth margin="normal">
                <InputLabel>Rollout Strategy</InputLabel>
                <Select
                  value={rolloutStrategy}
                  onChange={(e) => setRolloutStrategy(e.target.value)}
                >
                  <MenuItem value="immediate">Immediate</MenuItem>
                  <MenuItem value="progressive">Progressive</MenuItem>
                  <MenuItem value="canary">Canary</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            {rolloutStrategy === 'progressive' && (
              <>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Rollout Phases (%)"
                    value={rolloutPhases.join(', ')}
                    onChange={(e) => {
                      const phases = e.target.value.split(',').map(p => parseInt(p.trim())).filter(p => !isNaN(p));
                      setRolloutPhases(phases);
                    }}
                    margin="normal"
                    helperText="Comma-separated percentages (e.g., 10, 30, 70, 100)"
                  />
                </Grid>
                
                <Grid item xs={6}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Phase Duration (hours)"
                    value={phaseDuration}
                    onChange={(e) => setPhaseDuration(parseInt(e.target.value))}
                    margin="normal"
                  />
                </Grid>
                
                <Grid item xs={6}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Rollback Threshold (%)"
                    value={rollbackThreshold}
                    onChange={(e) => setRollbackThreshold(parseFloat(e.target.value))}
                    margin="normal"
                    inputProps={{ step: 0.1 }}
                  />
                </Grid>
                
                <Grid item xs={12}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={healthCheckEnabled}
                        onChange={(e) => setHealthCheckEnabled(e.target.checked)}
                      />
                    }
                    label="Enable health checks"
                  />
                  <FormControlLabel
                    control={
                      <Switch
                        checked={approvalRequired}
                        onChange={(e) => setApprovalRequired(e.target.checked)}
                      />
                    }
                    label="Require manual approval between phases"
                  />
                </Grid>
              </>
            )}
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDistDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleCreateDistribution}
            variant="contained"
            disabled={!snapName.trim() || selectedDevices.length === 0 || loading}
          >
            {loading ? <CircularProgress size={20} /> : 'Create Distribution'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Register Store Proxy Dialog */}
      <Dialog open={proxyDialogOpen} onClose={() => setProxyDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Register Store Proxy</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Proxy ID"
            value={proxyId}
            onChange={(e) => setProxyId(e.target.value)}
            margin="normal"
            placeholder="e.g., main-proxy, edge-proxy"
          />
          <TextField
            fullWidth
            label="Proxy Endpoint"
            value={proxyEndpoint}
            onChange={(e) => setProxyEndpoint(e.target.value)}
            margin="normal"
            placeholder="https://snap-proxy.example.com"
          />
          <TextField
            fullWidth
            label="Authentication Token (optional)"
            type="password"
            value={proxyAuthToken}
            onChange={(e) => setProxyAuthToken(e.target.value)}
            margin="normal"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setProxyDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleRegisterProxy}
            variant="contained"
            disabled={!proxyId.trim() || !proxyEndpoint.trim() || loading}
          >
            Register
          </Button>
        </DialogActions>
      </Dialog>

      {/* Distribution Details Dialog */}
      <Dialog 
        open={logsDialogOpen} 
        onClose={() => setLogsDialogOpen(false)} 
        maxWidth="lg" 
        fullWidth
      >
        <DialogTitle>
          Distribution Details: {selectedDistribution?.snap_name}
        </DialogTitle>
        <DialogContent>
          {selectedDistribution && (
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>Status</Typography>
                <Chip 
                  label={selectedDistribution.status} 
                  color={getStatusColor(selectedDistribution.status)}
                  sx={{ mb: 2 }}
                />
                
                <Typography variant="subtitle2" gutterBottom>Progress</Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={selectedDistribution.progress_percent} 
                  sx={{ mb: 1 }}
                />
                <Typography variant="body2" gutterBottom>
                  {selectedDistribution.progress_percent.toFixed(1)}% 
                  ({selectedDistribution.devices_updated} / {selectedDistribution.devices_targeted} devices)
                </Typography>
                
                <Typography variant="subtitle2" gutterBottom>Phase</Typography>
                <Typography variant="body2" gutterBottom>
                  {selectedDistribution.current_phase + 1} of {selectedDistribution.total_phases}
                </Typography>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>Health Metrics</Typography>
                {Object.keys(selectedDistribution.health_metrics).length > 0 ? (
                  Object.entries(selectedDistribution.health_metrics).map(([key, value]) => (
                    <Typography key={key} variant="body2">
                      {key}: {String(value)}
                    </Typography>
                  ))
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No health metrics available
                  </Typography>
                )}
              </Grid>
              
              {selectedDistribution.errors.length > 0 && (
                <Grid item xs={12}>
                  <Typography variant="subtitle2" gutterBottom>Errors</Typography>
                  <List dense>
                    {selectedDistribution.errors.map((error, index) => (
                      <ListItem key={index}>
                        <ListItemIcon>
                          <ErrorIcon color="error" fontSize="small" />
                        </ListItemIcon>
                        <ListItemText primary={error} />
                      </ListItem>
                    ))}
                  </List>
                </Grid>
              )}
            </Grid>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLogsDialogOpen(false)}>Close</Button>
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

export default SnapDistributionManager;