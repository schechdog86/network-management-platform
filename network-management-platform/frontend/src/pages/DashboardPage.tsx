import React, { useEffect } from 'react';
import { Box, Grid, Typography, Paper, Alert } from '@mui/material';
import { useMetricsStore } from '@/stores/metricsStore';
import { useDeviceStore } from '@/stores/deviceStore';
import SystemMetricsGrid from '@/components/Dashboard/SystemMetricsGrid';
import NetworkTopologyChart from '@/components/Dashboard/NetworkTopologyChart';
import LoadingSpinner from '@/components/Common/LoadingSpinner';

const DashboardPage: React.FC = () => {
  const [initialLoading, setInitialLoading] = React.useState(true);
  
  const {
    currentMetrics,
    metricsHistory,
    isCollecting,
    fetchCurrentMetrics,
    fetchCollectionStatus,
    startCollection,
    error: metricsError,
    clearError: clearMetricsError
  } = useMetricsStore();

  const {
    devices,
    fetchDevices,
    error: devicesError,
    clearError: clearDevicesError
  } = useDeviceStore();

  // Initialize data on component mount
  useEffect(() => {
    const initializeDashboard = async () => {
      try {
        // Fetch initial data
        await Promise.all([
          fetchDevices(),
          fetchCurrentMetrics(),
          fetchCollectionStatus()
        ]);

        // Start metrics collection if not already running
        if (!isCollecting) {
          await startCollection(5); // 5-second interval
        }
      } catch (error) {
        console.error('Failed to initialize dashboard:', error);
      } finally {
        setInitialLoading(false);
      }
    };

    initializeDashboard();
  }, [fetchDevices, fetchCurrentMetrics, fetchCollectionStatus, startCollection, isCollecting]);

  // Periodically refresh current metrics
  useEffect(() => {
    const interval = setInterval(() => {
      if (!isCollecting) {
        fetchCurrentMetrics();
      }
    }, 10000); // Refresh every 10 seconds if real-time collection is not active

    return () => clearInterval(interval);
  }, [fetchCurrentMetrics, isCollecting]);

  const handleErrorDismiss = () => {
    clearMetricsError();
    clearDevicesError();
  };

  if (initialLoading) {
    return <LoadingSpinner message="Loading dashboard data..." />;
  }

  return (
    <Box>
      {/* Header */}
      <Box mb={3}>
        <Typography variant="h4" component="h1" gutterBottom>
          Network Management Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Real-time monitoring and management of your network infrastructure
        </Typography>
      </Box>

      {/* Error Alerts */}
      {(metricsError || devicesError) && (
        <Alert 
          severity="error" 
          onClose={handleErrorDismiss}
          sx={{ mb: 3 }}
        >
          {metricsError || devicesError}
        </Alert>
      )}

      {/* Collection Status */}
      {!isCollecting && (
        <Alert 
          severity="warning" 
          sx={{ mb: 3 }}
        >
          Real-time metrics collection is not active. Data may not be current.
        </Alert>
      )}

      {/* Main Content */}
      <Grid container spacing={3}>
        {/* System Metrics Section */}
        <Grid item xs={12}>
          <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
            <Typography variant="h5" component="h2" gutterBottom>
              System Performance
            </Typography>
            <SystemMetricsGrid 
              currentMetrics={currentMetrics}
              metricsHistory={metricsHistory}
            />
          </Paper>
        </Grid>

        {/* Network Overview Section */}
        <Grid item xs={12}>
          <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
            <Typography variant="h5" component="h2" gutterBottom>
              Network Overview
            </Typography>
            <NetworkTopologyChart devices={devices} />
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardPage;