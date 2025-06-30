import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  LinearProgress,
  Alert,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  CircularProgress,
} from '@mui/material';
import {
  Computer as ComputerIcon,
  Memory as MemoryIcon,
  Gpu as GpuIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
  Info as InfoIcon,
  Assignment as TaskIcon,
  Theaters as ActorIcon,
  Timeline as TimelineIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import api from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';

interface RayWorker {
  node_id: string;
  worker_id?: string;
  status: string;
  timestamp: string;
  last_update: string;
  resources?: {
    cpus?: number;
    gpus?: number;
    memory?: number;
  };
  labels?: Record<string, string>;
  error?: string;
}

interface WorkerTask {
  task_id: string;
  node_id: string;
  status: string;
  duration_seconds: number;
  start_time: string;
  end_time: string;
  error?: string;
}

interface WorkerActor {
  actor_name: string;
  node_id: string;
  status: string;
  registered_at: string;
}

interface WorkerStats {
  workers: {
    total: number;
    by_status: Record<string, number>;
    resources: {
      cpus: number;
      gpus: number;
      memory: number;
    };
  };
  tasks: {
    total: number;
    success: number;
    failed: number;
    timeout: number;
    average_duration_seconds: number;
  };
  actors: {
    total: number;
  };
}

const RayWorkerDashboard: React.FC = () => {
  const [workers, setWorkers] = useState<RayWorker[]>([]);
  const [stats, setStats] = useState<WorkerStats | null>(null);
  const [selectedWorker, setSelectedWorker] = useState<RayWorker | null>(null);
  const [workerDetails, setWorkerDetails] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const { lastMessage } = useWebSocket();

  useEffect(() => {
    fetchWorkers();
    fetchStats();
  }, []);

  useEffect(() => {
    // Handle real-time updates
    if (lastMessage) {
      try {
        const data = JSON.parse(lastMessage);
        if (data.type === 'ray_worker_status' || 
            data.type === 'ray_task_complete' ||
            data.type === 'ray_actor_registered') {
          // Refresh data on updates
          fetchWorkers();
          fetchStats();
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    }
  }, [lastMessage]);

  const fetchWorkers = async () => {
    try {
      const response = await api.get('/api/v1/ray-worker/list');
      setWorkers(response.data.workers);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching workers:', error);
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await api.get('/api/v1/ray-worker/stats/summary');
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const fetchWorkerDetails = async (nodeId: string) => {
    try {
      const response = await api.get(`/api/v1/ray-worker/${nodeId}`);
      setWorkerDetails(response.data);
    } catch (error) {
      console.error('Error fetching worker details:', error);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([fetchWorkers(), fetchStats()]);
    setRefreshing(false);
  };

  const handleViewDetails = async (worker: RayWorker) => {
    setSelectedWorker(worker);
    setDetailsOpen(true);
    setWorkerDetails(null);
    await fetchWorkerDetails(worker.node_id);
  };

  const handleDeleteWorker = async (nodeId: string) => {
    if (!window.confirm(`Are you sure you want to remove worker ${nodeId}?`)) {
      return;
    }

    try {
      await api.delete(`/api/v1/ray-worker/${nodeId}`);
      await fetchWorkers();
      await fetchStats();
    } catch (error) {
      console.error('Error deleting worker:', error);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'connected':
        return <CheckCircleIcon color="success" />;
      case 'failed':
        return <ErrorIcon color="error" />;
      case 'shutting_down':
        return <WarningIcon color="warning" />;
      default:
        return <InfoIcon color="info" />;
    }
  };

  const getStatusColor = (status: string): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
    switch (status) {
      case 'connected':
        return 'success';
      case 'failed':
        return 'error';
      case 'shutting_down':
        return 'warning';
      default:
        return 'default';
    }
  };

  const formatMemory = (bytes?: number) => {
    if (!bytes) return 'N/A';
    const gb = bytes / (1024 ** 3);
    return `${gb.toFixed(1)} GB`;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={400}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5">Ray Worker Dashboard</Typography>
        <Tooltip title="Refresh data">
          <IconButton onClick={handleRefresh} disabled={refreshing}>
            <RefreshIcon className={refreshing ? 'rotating' : ''} />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Statistics Cards */}
      {stats && (
        <Grid container spacing={3} mb={3}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" gutterBottom>
                  Total Workers
                </Typography>
                <Typography variant="h4">
                  {stats.workers.total}
                </Typography>
                <Box mt={1}>
                  {Object.entries(stats.workers.by_status).map(([status, count]) => (
                    <Chip
                      key={status}
                      label={`${status}: ${count}`}
                      size="small"
                      color={getStatusColor(status)}
                      sx={{ mr: 0.5 }}
                    />
                  ))}
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" gutterBottom>
                  Resources
                </Typography>
                <List dense>
                  <ListItem>
                    <ListItemIcon>
                      <MemoryIcon />
                    </ListItemIcon>
                    <ListItemText primary={`CPUs: ${stats.workers.resources.cpus}`} />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon>
                      <GpuIcon />
                    </ListItemIcon>
                    <ListItemText primary={`GPUs: ${stats.workers.resources.gpus}`} />
                  </ListItem>
                  <ListItem>
                    <ListItemText 
                      primary={`Memory: ${formatMemory(stats.workers.resources.memory)}`} 
                    />
                  </ListItem>
                </List>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" gutterBottom>
                  Tasks
                </Typography>
                <Typography variant="h4">
                  {stats.tasks.total}
                </Typography>
                <Box mt={1}>
                  <LinearProgress
                    variant="determinate"
                    value={(stats.tasks.success / stats.tasks.total) * 100 || 0}
                    sx={{ mb: 1 }}
                  />
                  <Typography variant="caption">
                    Success Rate: {((stats.tasks.success / stats.tasks.total) * 100 || 0).toFixed(1)}%
                  </Typography>
                  <Typography variant="caption" display="block">
                    Avg Duration: {stats.tasks.average_duration_seconds.toFixed(2)}s
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" gutterBottom>
                  Actors
                </Typography>
                <Typography variant="h4">
                  {stats.actors.total}
                </Typography>
                <Typography variant="body2" color="text.secondary" mt={1}>
                  Named actors registered
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Workers Table */}
      <Paper elevation={1}>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Node ID</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Resources</TableCell>
                <TableCell>Labels</TableCell>
                <TableCell>Last Update</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {workers.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography color="text.secondary" py={3}>
                      No Ray workers registered
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                workers.map((worker) => (
                  <TableRow key={worker.node_id}>
                    <TableCell>
                      <Box display="flex" alignItems="center">
                        <ComputerIcon sx={{ mr: 1 }} />
                        <Typography variant="body2">{worker.node_id}</Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        icon={getStatusIcon(worker.status)}
                        label={worker.status}
                        size="small"
                        color={getStatusColor(worker.status)}
                      />
                    </TableCell>
                    <TableCell>
                      <Box>
                        {worker.resources?.cpus && (
                          <Typography variant="caption" display="block">
                            CPUs: {worker.resources.cpus}
                          </Typography>
                        )}
                        {worker.resources?.gpus && (
                          <Typography variant="caption" display="block">
                            GPUs: {worker.resources.gpus}
                          </Typography>
                        )}
                        {worker.resources?.memory && (
                          <Typography variant="caption" display="block">
                            Memory: {formatMemory(worker.resources.memory)}
                          </Typography>
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>
                      {worker.labels && Object.entries(worker.labels).map(([key, value]) => (
                        <Chip
                          key={key}
                          label={`${key}: ${value}`}
                          size="small"
                          sx={{ mr: 0.5, mb: 0.5 }}
                        />
                      ))}
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption">
                        {format(new Date(worker.last_update), 'MMM d, HH:mm:ss')}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="View details">
                        <IconButton
                          size="small"
                          onClick={() => handleViewDetails(worker)}
                        >
                          <InfoIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Remove worker">
                        <IconButton
                          size="small"
                          onClick={() => handleDeleteWorker(worker.node_id)}
                          color="error"
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* Worker Details Dialog */}
      <Dialog
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          Worker Details: {selectedWorker?.node_id}
        </DialogTitle>
        <DialogContent>
          {!workerDetails ? (
            <Box display="flex" justifyContent="center" py={3}>
              <CircularProgress />
            </Box>
          ) : (
            <Box>
              {/* Worker Info */}
              <Typography variant="h6" gutterBottom>
                Worker Information
              </Typography>
              <List>
                <ListItem>
                  <ListItemText
                    primary="Worker ID"
                    secondary={workerDetails.worker.worker_id || 'N/A'}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Status"
                    secondary={workerDetails.worker.status}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Last Update"
                    secondary={format(new Date(workerDetails.worker.last_update), 'PPpp')}
                  />
                </ListItem>
              </List>

              <Divider sx={{ my: 2 }} />

              {/* Recent Tasks */}
              <Typography variant="h6" gutterBottom>
                Recent Tasks
              </Typography>
              {workerDetails.recent_tasks.length === 0 ? (
                <Typography color="text.secondary">No tasks recorded</Typography>
              ) : (
                <List dense>
                  {workerDetails.recent_tasks.map((task: WorkerTask) => (
                    <ListItem key={task.task_id}>
                      <ListItemIcon>
                        {task.status === 'success' ? (
                          <CheckCircleIcon color="success" />
                        ) : (
                          <ErrorIcon color="error" />
                        )}
                      </ListItemIcon>
                      <ListItemText
                        primary={task.task_id}
                        secondary={`Duration: ${task.duration_seconds.toFixed(2)}s - ${format(new Date(task.start_time), 'HH:mm:ss')}`}
                      />
                    </ListItem>
                  ))}
                </List>
              )}

              <Divider sx={{ my: 2 }} />

              {/* Actors */}
              <Typography variant="h6" gutterBottom>
                Actors
              </Typography>
              {workerDetails.actors.length === 0 ? (
                <Typography color="text.secondary">No actors registered</Typography>
              ) : (
                <List dense>
                  {workerDetails.actors.map((actor: WorkerActor) => (
                    <ListItem key={actor.actor_name}>
                      <ListItemIcon>
                        <ActorIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary={actor.actor_name}
                        secondary={`Registered: ${format(new Date(actor.registered_at), 'PPp')}`}
                      />
                    </ListItem>
                  ))}
                </List>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailsOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default RayWorkerDashboard;