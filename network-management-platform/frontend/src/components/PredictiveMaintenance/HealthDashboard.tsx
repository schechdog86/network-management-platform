import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  LinearProgress,
  Chip,
  IconButton,
  Tooltip,
  Alert,
  Button,
  CircularProgress,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Warning,
  CheckCircle,
  Schedule,
  Refresh,
  BugReport,
} from '@mui/icons-material';
import { Line } from 'react-chartjs-2';
import { api } from '../../services/api';

interface HealthData {
  device_id: string;
  health_score: number;
  status: string;
  anomalies: any[];
  predictions: any[];
  recommendations: any[];
}

interface DeviceHealthProps {
  deviceId: string;
  deviceName?: string;
}

export const DeviceHealthCard: React.FC<DeviceHealthProps> = ({ deviceId, deviceName }) => {
  const [healthData, setHealthData] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealthData = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/api/v1/predictive-maintenance/health/${deviceId}`);
      setHealthData(response.data);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch health data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealthData();
    const interval = setInterval(fetchHealthData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, [deviceId]);

  const getHealthColor = (score: number) => {
    if (score >= 90) return '#4caf50';
    if (score >= 75) return '#8bc34a';
    if (score >= 60) return '#ff9800';
    if (score >= 40) return '#ff5722';
    return '#f44336';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'excellent':
      case 'good':
        return <CheckCircle sx={{ color: 'success.main' }} />;
      case 'fair':
        return <Warning sx={{ color: 'warning.main' }} />;
      case 'poor':
      case 'critical':
        return <Warning sx={{ color: 'error.main' }} />;
      default:
        return null;
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Alert severity="error">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  if (!healthData) return null;

  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            {deviceName || deviceId}
          </Typography>
          <IconButton size="small" onClick={fetchHealthData}>
            <Refresh />
          </IconButton>
        </Box>

        {/* Health Score */}
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
              Health Score
            </Typography>
            {getStatusIcon(healthData.status)}
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <LinearProgress
              variant="determinate"
              value={healthData.health_score}
              sx={{
                flex: 1,
                height: 10,
                borderRadius: 5,
                mr: 2,
                '& .MuiLinearProgress-bar': {
                  backgroundColor: getHealthColor(healthData.health_score),
                },
              }}
            />
            <Typography variant="h6" sx={{ minWidth: 50 }}>
              {healthData.health_score}%
            </Typography>
          </Box>
          <Chip
            label={healthData.status.toUpperCase()}
            size="small"
            sx={{
              mt: 1,
              backgroundColor: getHealthColor(healthData.health_score),
              color: 'white',
            }}
          />
        </Box>

        {/* Anomalies */}
        {healthData.anomalies.length > 0 && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              <BugReport sx={{ fontSize: 16, mr: 0.5, verticalAlign: 'middle' }} />
              Anomalies Detected
            </Typography>
            {healthData.anomalies.map((anomaly, index) => (
              <Alert severity="warning" sx={{ mb: 1 }} key={index}>
                {anomaly.type} - {anomaly.severity}
              </Alert>
            ))}
          </Box>
        )}

        {/* Predictions */}
        {healthData.predictions.length > 0 && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              <TrendingUp sx={{ fontSize: 16, mr: 0.5, verticalAlign: 'middle' }} />
              Failure Predictions
            </Typography>
            {healthData.predictions.map((prediction, index) => (
              <Alert 
                severity={prediction.severity === 'critical' ? 'error' : 'warning'} 
                sx={{ mb: 1 }} 
                key={index}
              >
                {prediction.metric} will reach critical in {prediction.days_until_issue} days
              </Alert>
            ))}
          </Box>
        )}

        {/* Recommendations */}
        {healthData.recommendations.length > 0 && (
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              <Schedule sx={{ fontSize: 16, mr: 0.5, verticalAlign: 'middle' }} />
              Maintenance Recommendations
            </Typography>
            {healthData.recommendations.map((rec, index) => (
              <Box key={index} sx={{ mb: 1 }}>
                <Chip
                  label={rec.priority}
                  size="small"
                  color={rec.priority === 'high' ? 'error' : rec.priority === 'medium' ? 'warning' : 'default'}
                  sx={{ mr: 1 }}
                />
                <Typography variant="body2" component="span">
                  {rec.action}
                </Typography>
              </Box>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

interface FleetHealthDashboardProps {
  deviceIds: string[];
}

export const FleetHealthDashboard: React.FC<FleetHealthDashboardProps> = ({ deviceIds }) => {
  const [fleetData, setFleetData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchFleetHealth = async () => {
    try {
      setLoading(true);
      const response = await api.post('/api/v1/predictive-maintenance/analyze-fleet', {
        device_ids: deviceIds,
      });
      setFleetData(response.data);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch fleet health');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (deviceIds.length > 0) {
      fetchFleetHealth();
    }
  }, [deviceIds]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  if (!fleetData) return null;

  const { fleet_summary } = fleetData;

  return (
    <Grid container spacing={3}>
      <Grid item xs={12}>
        <Card>
          <CardContent>
            <Typography variant="h5" gutterBottom>
              Fleet Health Overview
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} md={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h3" color="primary">
                    {fleet_summary.total_devices}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Total Devices
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} md={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h3" sx={{ color: '#4caf50' }}>
                    {fleet_summary.healthy_devices}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Healthy Devices
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} md={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h3" sx={{ color: '#ff5722' }}>
                    {fleet_summary.at_risk_devices}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    At Risk Devices
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} md={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <CircularProgress
                    variant="determinate"
                    value={fleet_summary.health_percentage}
                    size={80}
                    thickness={4}
                    sx={{
                      color: fleet_summary.health_percentage >= 75 ? '#4caf50' : '#ff9800',
                    }}
                  />
                  <Typography variant="h6" sx={{ mt: 1 }}>
                    {fleet_summary.health_percentage}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Fleet Health
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </Grid>

      {/* Individual device cards */}
      {Object.entries(fleetData.device_results).map(([deviceId, deviceData]: [string, any]) => (
        <Grid item xs={12} md={6} lg={4} key={deviceId}>
          <DeviceHealthCard deviceId={deviceId} />
        </Grid>
      ))}
    </Grid>
  );
};

interface MaintenanceScheduleProps {
  deviceIds: string[];
}

export const MaintenanceSchedule: React.FC<MaintenanceScheduleProps> = ({ deviceIds }) => {
  const [schedule, setSchedule] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateSchedule = async () => {
    try {
      setLoading(true);
      const response = await api.post('/api/v1/predictive-maintenance/maintenance-schedule', {
        device_ids: deviceIds,
      });
      setSchedule(response.data);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate schedule');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Maintenance Schedule Generator
        </Typography>
        
        <Button
          variant="contained"
          onClick={generateSchedule}
          disabled={loading || deviceIds.length === 0}
          startIcon={loading ? <CircularProgress size={20} /> : <Schedule />}
        >
          Generate Optimized Schedule
        </Button>

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}

        {schedule && (
          <Box sx={{ mt: 3 }}>
            <Alert severity="info" sx={{ mb: 2 }}>
              Total maintenance windows: {schedule.schedule.length} | 
              Estimated downtime: {schedule.estimated_total_downtime} minutes
            </Alert>

            {schedule.schedule.map((window: any, index: number) => (
              <Card key={index} sx={{ mb: 2, bgcolor: 'grey.50' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="subtitle1">
                      Maintenance Window {index + 1}
                    </Typography>
                    <Chip
                      label={`Priority: ${window.priority}`}
                      size="small"
                      color={window.priority >= 8 ? 'error' : window.priority >= 5 ? 'warning' : 'default'}
                    />
                  </Box>
                  <Typography variant="body2" color="text.secondary">
                    Recommended Date: {new Date(window.recommended_date).toLocaleDateString()}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Duration: {window.estimated_duration} minutes
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    Devices: {window.device_ids ? window.device_ids.join(', ') : window.device_id}
                  </Typography>
                </CardContent>
              </Card>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};