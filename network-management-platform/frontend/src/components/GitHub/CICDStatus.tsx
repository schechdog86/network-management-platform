import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  LinearProgress,
  IconButton,
  Tooltip,
  Button,
  Alert,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  CircularProgress,
  Stack,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Cancel as CancelIcon,
  Schedule as ScheduleIcon,
  PlayArrow as PlayArrowIcon,
  Refresh as RefreshIcon,
  CloudUpload as DeployIcon,
  Speed as SpeedIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import api from '../../services/api';

interface DeploymentRecord {
  workflow_id: string;
  workflow_name: string;
  run_number: number;
  environment: string;
  status: string;
  started_at: string;
  updated_at: string;
  commit_sha: string;
  branch: string;
}

interface CICDSummary {
  deployments: {
    latest_deployments: Record<string, DeploymentRecord>;
    statistics: {
      total_deployments: number;
      successful_deployments: number;
      failed_deployments: number;
      success_rate: number;
    };
    recent_deployments: DeploymentRecord[];
  };
  workflows: {
    total_runs: number;
    average_duration_seconds: number;
    success_rate: number;
    workflows_by_status: {
      in_progress: number;
      successful: number;
      failed: number;
      cancelled: number;
    };
  };
  monitoring_active: boolean;
  last_check: string | null;
}

const CICDStatus: React.FC = () => {
  const [summary, setSummary] = useState<CICDSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [deploying, setDeploying] = useState<string | null>(null);

  const fetchCICDStatus = async () => {
    try {
      setError(null);
      const response = await api.get('/api/v1/cicd/status/summary');
      setSummary(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch CI/CD status');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchCICDStatus();
    // Refresh every 2 minutes
    const interval = setInterval(fetchCICDStatus, 2 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchCICDStatus();
  };

  const handleDeploy = async (environment: string) => {
    setDeploying(environment);
    try {
      await api.post('/api/v1/cicd/deployments/trigger', {
        environment,
        branch: 'main',
      });
      // Refresh status after triggering deployment
      setTimeout(fetchCICDStatus, 5000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to trigger deployment');
    } finally {
      setDeploying(null);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'success':
        return <CheckCircleIcon color="success" />;
      case 'failed':
        return <ErrorIcon color="error" />;
      case 'cancelled':
        return <CancelIcon color="warning" />;
      case 'in_progress':
        return <CircularProgress size={20} />;
      default:
        return <ScheduleIcon color="disabled" />;
    }
  };

  const getEnvironmentColor = (env: string): 'default' | 'primary' | 'secondary' | 'success' => {
    switch (env.toLowerCase()) {
      case 'production':
        return 'success';
      case 'staging':
        return 'primary';
      case 'development':
        return 'secondary';
      default:
        return 'default';
    }
  };

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={400}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!summary) {
    return (
      <Alert severity="info" sx={{ m: 2 }}>
        No CI/CD data available
      </Alert>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5" gutterBottom>
          CI/CD Pipeline Status
        </Typography>
        <Tooltip title="Refresh data">
          <IconButton onClick={handleRefresh} disabled={refreshing}>
            <RefreshIcon className={refreshing ? 'rotating' : ''} />
          </IconButton>
        </Tooltip>
      </Box>

      <Grid container spacing={3}>
        {/* Deployment Statistics */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Deployment Statistics
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Box textAlign="center">
                    <Typography variant="h3" color="primary">
                      {summary.deployments.statistics.success_rate}%
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Success Rate
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box textAlign="center">
                    <Typography variant="h3">
                      {summary.deployments.statistics.total_deployments}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Deployments
                    </Typography>
                  </Box>
                </Grid>
              </Grid>

              <Box mt={2}>
                <Stack direction="row" spacing={1} justifyContent="center">
                  <Chip
                    icon={<CheckCircleIcon />}
                    label={`${summary.deployments.statistics.successful_deployments} Successful`}
                    color="success"
                    size="small"
                  />
                  <Chip
                    icon={<ErrorIcon />}
                    label={`${summary.deployments.statistics.failed_deployments} Failed`}
                    color="error"
                    size="small"
                  />
                </Stack>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Workflow Metrics */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Workflow Metrics
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Box textAlign="center">
                    <Typography variant="h3" color="secondary">
                      {summary.workflows.success_rate}%
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Build Success Rate
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box textAlign="center" display="flex" alignItems="center" justifyContent="center">
                    <SpeedIcon sx={{ mr: 1 }} />
                    <Typography variant="h4">
                      {formatDuration(summary.workflows.average_duration_seconds)}
                    </Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary" align="center">
                    Avg Duration
                  </Typography>
                </Grid>
              </Grid>

              <Box mt={2}>
                <Grid container spacing={1}>
                  <Grid item xs={3} textAlign="center">
                    <Typography variant="h6">{summary.workflows.workflows_by_status.in_progress}</Typography>
                    <Typography variant="caption" color="text.secondary">Running</Typography>
                  </Grid>
                  <Grid item xs={3} textAlign="center">
                    <Typography variant="h6" color="success.main">
                      {summary.workflows.workflows_by_status.successful}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">Success</Typography>
                  </Grid>
                  <Grid item xs={3} textAlign="center">
                    <Typography variant="h6" color="error.main">
                      {summary.workflows.workflows_by_status.failed}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">Failed</Typography>
                  </Grid>
                  <Grid item xs={3} textAlign="center">
                    <Typography variant="h6" color="warning.main">
                      {summary.workflows.workflows_by_status.cancelled}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">Cancelled</Typography>
                  </Grid>
                </Grid>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Environment Status */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Environment Status
              </Typography>
              
              <Grid container spacing={2}>
                {Object.entries(summary.deployments.latest_deployments).map(([env, deployment]) => (
                  <Grid item xs={12} md={4} key={env}>
                    <Card variant="outlined">
                      <CardContent>
                        <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                          <Chip
                            label={env.toUpperCase()}
                            color={getEnvironmentColor(env)}
                            size="small"
                          />
                          <IconButton
                            size="small"
                            onClick={() => handleDeploy(env)}
                            disabled={deploying === env}
                          >
                            {deploying === env ? (
                              <CircularProgress size={20} />
                            ) : (
                              <DeployIcon />
                            )}
                          </IconButton>
                        </Box>
                        
                        <Box display="flex" alignItems="center" mb={1}>
                          {getStatusIcon(deployment.status)}
                          <Typography variant="body2" sx={{ ml: 1 }}>
                            {deployment.status}
                          </Typography>
                        </Box>
                        
                        <Typography variant="caption" color="text.secondary" display="block">
                          Commit: {deployment.commit_sha}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" display="block">
                          Branch: {deployment.branch}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" display="block">
                          Updated: {format(new Date(deployment.updated_at), 'MMM d, HH:mm')}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Deployments */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Deployments
              </Typography>
              
              <List>
                {summary.deployments.recent_deployments.slice(0, 5).map((deployment) => (
                  <ListItem key={deployment.workflow_id}>
                    <ListItemIcon>
                      {getStatusIcon(deployment.status)}
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Box display="flex" alignItems="center" gap={1}>
                          <Typography variant="body2">
                            {deployment.workflow_name} #{deployment.run_number}
                          </Typography>
                          <Chip
                            label={deployment.environment}
                            size="small"
                            color={getEnvironmentColor(deployment.environment)}
                          />
                        </Box>
                      }
                      secondary={
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            {deployment.branch} • {deployment.commit_sha}
                          </Typography>
                          <Typography variant="caption" color="text.secondary" display="block">
                            {format(new Date(deployment.started_at), 'MMM d, yyyy HH:mm')}
                          </Typography>
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        {/* Monitoring Status */}
        <Grid item xs={12}>
          <Alert
            severity={summary.monitoring_active ? 'success' : 'warning'}
            icon={summary.monitoring_active ? <CheckCircleIcon /> : <ErrorIcon />}
          >
            CI/CD Monitoring is {summary.monitoring_active ? 'active' : 'inactive'}
            {summary.last_check && (
              <Typography variant="caption" display="block">
                Last check: {format(new Date(summary.last_check), 'MMM d, yyyy HH:mm:ss')}
              </Typography>
            )}
          </Alert>
        </Grid>
      </Grid>
    </Box>
  );
};

export default CICDStatus;