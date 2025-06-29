import React, { useMemo } from 'react';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
} from 'chart.js';
import { Doughnut, Bar } from 'react-chartjs-2';
import { Box, Paper, Typography, Grid, useTheme } from '@mui/material';
import { Device } from '@/types';

// Register Chart.js components
ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement);

interface NetworkTopologyChartProps {
  devices: Device[];
}

const NetworkTopologyChart: React.FC<NetworkTopologyChartProps> = ({ devices }) => {
  const theme = useTheme();

  // Device status distribution
  const statusData = useMemo(() => {
    const statusCounts = devices.reduce((acc, device) => {
      acc[device.status] = (acc[device.status] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    const colors = {
      online: theme.palette.success.main,
      offline: theme.palette.error.main,
      unknown: theme.palette.warning.main,
    };

    return {
      labels: Object.keys(statusCounts).map(status => 
        status.charAt(0).toUpperCase() + status.slice(1)
      ),
      datasets: [
        {
          data: Object.values(statusCounts),
          backgroundColor: Object.keys(statusCounts).map(status => 
            colors[status as keyof typeof colors] || theme.palette.grey[500]
          ),
          borderColor: theme.palette.background.paper,
          borderWidth: 2,
          hoverBorderWidth: 3,
        },
      ],
    };
  }, [devices, theme]);

  // Device type distribution
  const typeData = useMemo(() => {
    const typeCounts = devices.reduce((acc, device) => {
      const type = device.device_type || 'Unknown';
      acc[type] = (acc[type] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    const colorPalette = [
      theme.palette.primary.main,
      theme.palette.secondary.main,
      theme.palette.info.main,
      theme.palette.warning.main,
      theme.palette.error.main,
      theme.palette.success.main,
    ];

    return {
      labels: Object.keys(typeCounts),
      datasets: [
        {
          label: 'Device Count',
          data: Object.values(typeCounts),
          backgroundColor: Object.keys(typeCounts).map((_, index) => 
            colorPalette[index % colorPalette.length]
          ),
          borderColor: theme.palette.background.paper,
          borderWidth: 1,
          borderRadius: 4,
        },
      ],
    };
  }, [devices, theme]);

  const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom' as const,
        labels: {
          color: theme.palette.text.primary,
          padding: 20,
          usePointStyle: true,
          pointStyle: 'circle',
        },
      },
      tooltip: {
        backgroundColor: theme.palette.background.paper,
        titleColor: theme.palette.text.primary,
        bodyColor: theme.palette.text.primary,
        borderColor: theme.palette.divider,
        borderWidth: 1,
        cornerRadius: 8,
      },
    },
    cutout: '65%',
    elements: {
      arc: {
        borderWidth: 0,
      },
    },
  };

  const barOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: theme.palette.background.paper,
        titleColor: theme.palette.text.primary,
        bodyColor: theme.palette.text.primary,
        borderColor: theme.palette.divider,
        borderWidth: 1,
        cornerRadius: 8,
      },
    },
    scales: {
      x: {
        grid: {
          display: false,
        },
        ticks: {
          color: theme.palette.text.secondary,
        },
      },
      y: {
        grid: {
          color: theme.palette.divider,
        },
        ticks: {
          color: theme.palette.text.secondary,
          stepSize: 1,
        },
        beginAtZero: true,
      },
    },
  };

  // Network statistics
  const networkStats = useMemo(() => {
    const totalDevices = devices.length;
    const onlineDevices = devices.filter(d => d.status === 'online').length;
    const offlineDevices = devices.filter(d => d.status === 'offline').length;
    const unknownDevices = devices.filter(d => d.status === 'unknown').length;
    
    const snmpEnabled = devices.filter(d => d.snmp_enabled).length;
    const sshEnabled = devices.filter(d => d.ssh_enabled).length;
    
    const uniqueVendors = new Set(devices.map(d => d.vendor).filter(Boolean)).size;
    const uniqueTypes = new Set(devices.map(d => d.device_type).filter(Boolean)).size;

    return {
      totalDevices,
      onlineDevices,
      offlineDevices,
      unknownDevices,
      snmpEnabled,
      sshEnabled,
      uniqueVendors,
      uniqueTypes,
      uptimePercentage: totalDevices > 0 ? ((onlineDevices / totalDevices) * 100).toFixed(1) : '0',
    };
  }, [devices]);

  return (
    <Grid container spacing={3}>
      {/* Network Statistics */}
      <Grid item xs={12}>
        <Paper elevation={1} sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Network Overview
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={6} sm={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="primary">
                  {networkStats.totalDevices}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Total Devices
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="success.main">
                  {networkStats.onlineDevices}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Online
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="error.main">
                  {networkStats.offlineDevices}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Offline
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="info.main">
                  {networkStats.uptimePercentage}%
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Uptime
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Paper>
      </Grid>

      {/* Device Status Chart */}
      <Grid item xs={12} md={6}>
        <Paper elevation={1} sx={{ p: 2, height: 350 }}>
          <Typography variant="h6" gutterBottom>
            Device Status Distribution
          </Typography>
          <Box sx={{ height: 280 }}>
            {statusData.labels.length > 0 ? (
              <Doughnut data={statusData} options={doughnutOptions} />
            ) : (
              <Box 
                display="flex" 
                alignItems="center" 
                justifyContent="center" 
                height="100%"
              >
                <Typography variant="body2" color="text.secondary">
                  No devices found
                </Typography>
              </Box>
            )}
          </Box>
        </Paper>
      </Grid>

      {/* Device Type Chart */}
      <Grid item xs={12} md={6}>
        <Paper elevation={1} sx={{ p: 2, height: 350 }}>
          <Typography variant="h6" gutterBottom>
            Device Types
          </Typography>
          <Box sx={{ height: 280 }}>
            {typeData.labels.length > 0 ? (
              <Bar data={typeData} options={barOptions} />
            ) : (
              <Box 
                display="flex" 
                alignItems="center" 
                justifyContent="center" 
                height="100%"
              >
                <Typography variant="body2" color="text.secondary">
                  No device types available
                </Typography>
              </Box>
            )}
          </Box>
        </Paper>
      </Grid>

      {/* Additional Statistics */}
      <Grid item xs={12}>
        <Paper elevation={1} sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Management Capabilities
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={6} sm={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="warning.main">
                  {networkStats.snmpEnabled}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  SNMP Enabled
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="info.main">
                  {networkStats.sshEnabled}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  SSH Enabled
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="secondary.main">
                  {networkStats.uniqueVendors}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Unique Vendors
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="primary.main">
                  {networkStats.uniqueTypes}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Device Types
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Paper>
      </Grid>
    </Grid>
  );
};

export default NetworkTopologyChart;