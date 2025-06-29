import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  Grid,
  Alert,
  Switch,
  FormControlLabel,
  TextField,
  MenuItem,
} from '@mui/material';
import {
  PlayArrow as StartIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';
import { useMetricsStore } from '@/stores/metricsStore';
import SystemMetricsGrid from '@/components/Dashboard/SystemMetricsGrid';
import LoadingSpinner from '@/components/Common/LoadingSpinner';

const MetricsPage: React.FC = () => {
  const {
    currentMetrics,
    metricsHistory,
    isCollecting,
    collectionStatus,
    isLoading,
    error,
    fetchCurrentMetrics,
    fetchMetricsHistory,
    fetchCollectionStatus,
    startCollection,
    stopCollection,
    clearError,
  } = useMetricsStore();

  const [historyHours, setHistoryHours] = useState(1);
  const [collectionInterval, setCollectionInterval] = useState(5);

  useEffect(() => {
    const initializeMetrics = async () => {
      await Promise.all([
        fetchCurrentMetrics(),
        fetchCollectionStatus(),
        fetchMetricsHistory(historyHours),
      ]);
    };

    initializeMetrics();
  }, [fetchCurrentMetrics, fetchCollectionStatus, fetchMetricsHistory, historyHours]);

  const handleStartCollection = async () => {
    await startCollection(collectionInterval);
  };

  const handleStopCollection = async () => {
    await stopCollection();
  };

  const handleRefreshMetrics = async () => {
    await fetchCurrentMetrics();
  };

  const handleRefreshHistory = async () => {
    await fetchMetricsHistory(historyHours);
  };

  const handleExportData = () => {
    // TODO: Implement data export functionality
    const data = {
      currentMetrics,
      metricsHistory,
      exportedAt: new Date().toISOString(),
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `metrics-export-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (isLoading && !currentMetrics && metricsHistory.length === 0) {
    return <LoadingSpinner message="Loading metrics..." />;
  }

  return (
    <Box>
      {/* Header */}
      <Box mb={3}>
        <Typography variant="h4" component="h1" gutterBottom>
          System Metrics
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Monitor system performance and resource utilization
        </Typography>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert 
          severity="error" 
          onClose={clearError}
          sx={{ mb: 3 }}
        >
          {error}
        </Alert>
      )}

      {/* Collection Status Alert */}
      {!isCollecting && (
        <Alert 
          severity="info" 
          sx={{ mb: 3 }}
        >
          Real-time metrics collection is currently stopped. Start collection to see live updates.
        </Alert>
      )}

      {/* Control Panel */}
      <Paper elevation={1} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Metrics Collection Control
        </Typography>
        
        <Grid container spacing={3} alignItems="center">
          {/* Collection Status */}
          <Grid item xs={12} md={3}>
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Collection Status
              </Typography>
              <FormControlLabel
                control={
                  <Switch
                    checked={isCollecting}
                    onChange={isCollecting ? handleStopCollection : handleStartCollection}
                    disabled={isLoading}
                  />
                }
                label={isCollecting ? 'Active' : 'Stopped'}
              />
            </Box>
          </Grid>

          {/* Collection Interval */}
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              label="Collection Interval (seconds)"
              type="number"
              value={collectionInterval}
              onChange={(e) => setCollectionInterval(Number(e.target.value))}
              disabled={isCollecting}
              inputProps={{ min: 1, max: 60 }}
              helperText="1-60 seconds"
            />
          </Grid>

          {/* History Range */}
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              select
              label="History Range"
              value={historyHours}
              onChange={(e) => setHistoryHours(Number(e.target.value))}
            >
              <MenuItem value={1}>Last Hour</MenuItem>
              <MenuItem value={6}>Last 6 Hours</MenuItem>
              <MenuItem value={24}>Last 24 Hours</MenuItem>
              <MenuItem value={168}>Last Week</MenuItem>
            </TextField>
          </Grid>

          {/* Actions */}
          <Grid item xs={12} md={3}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={handleRefreshMetrics}
                disabled={isLoading}
                size="small"
              >
                Refresh Current
              </Button>
              <Button
                variant="outlined"
                startIcon={<DownloadIcon />}
                onClick={handleExportData}
                disabled={!currentMetrics && metricsHistory.length === 0}
                size="small"
              >
                Export Data
              </Button>
            </Box>
          </Grid>
        </Grid>

        {/* Collection Information */}
        {collectionStatus && (
          <Box sx={{ mt: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Grid container spacing={2}>
              <Grid item xs={6} sm={3}>
                <Typography variant="body2" color="text.secondary">
                  Status
                </Typography>
                <Typography variant="body2" fontWeight="medium">
                  {collectionStatus.is_collecting ? 'Active' : 'Stopped'}
                </Typography>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Typography variant="body2" color="text.secondary">
                  Interval
                </Typography>
                <Typography variant="body2" fontWeight="medium">
                  {collectionStatus.collection_interval}s
                </Typography>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Typography variant="body2" color="text.secondary">
                  History Size
                </Typography>
                <Typography variant="body2" fontWeight="medium">
                  {collectionStatus.history_size} / {collectionStatus.max_history_size}
                </Typography>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Typography variant="body2" color="text.secondary">
                  Task Status
                </Typography>
                <Typography variant="body2" fontWeight="medium">
                  {collectionStatus.task_active ? 'Running' : 'Idle'}
                </Typography>
              </Grid>
            </Grid>
          </Box>
        )}
      </Paper>

      {/* Metrics Visualization */}
      {(currentMetrics || metricsHistory.length > 0) ? (
        <Paper elevation={0} sx={{ p: 3, bgcolor: 'background.default' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Typography variant="h6">
              System Performance Overview
            </Typography>
            <Button
              variant="text"
              startIcon={<RefreshIcon />}
              onClick={handleRefreshHistory}
              disabled={isLoading}
            >
              Refresh History
            </Button>
          </Box>
          
          <SystemMetricsGrid 
            currentMetrics={currentMetrics}
            metricsHistory={metricsHistory}
          />
        </Paper>
      ) : (
        <Paper 
          elevation={0} 
          sx={{ 
            p: 6, 
            textAlign: 'center',
            bgcolor: 'background.default'
          }}
        >
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No metrics data available
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Start metrics collection to begin monitoring system performance
          </Typography>
          <Button
            variant="contained"
            startIcon={<StartIcon />}
            onClick={handleStartCollection}
            disabled={isLoading}
          >
            Start Collection
          </Button>
        </Paper>
      )}
    </Box>
  );
};

export default MetricsPage;