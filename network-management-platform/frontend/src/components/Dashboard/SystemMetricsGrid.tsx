import React, { useMemo } from 'react';
import { Grid, Box } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import MetricsChart from './MetricsChart';
import CircularProgressChart from './CircularProgressChart';
import { SystemMetrics } from '@/types';

interface SystemMetricsGridProps {
  currentMetrics: SystemMetrics | null;
  metricsHistory: SystemMetrics[];
}

const SystemMetricsGrid: React.FC<SystemMetricsGridProps> = ({
  currentMetrics,
  metricsHistory,
}) => {
  const theme = useTheme();

  // Transform metrics history for chart data
  const cpuData = useMemo(() => 
    metricsHistory.map(m => ({
      timestamp: m.timestamp,
      value: m.cpu?.usage_percent || 0,
    }))
  , [metricsHistory]);

  const memoryData = useMemo(() => 
    metricsHistory.map(m => ({
      timestamp: m.timestamp,
      value: m.memory?.virtual?.percent || 0,
    }))
  , [metricsHistory]);

  const networkInData = useMemo(() => 
    metricsHistory.map(m => ({
      timestamp: m.timestamp,
      value: (m.network?.total_io?.bytes_recv || 0) / (1024 * 1024), // Convert to MB
    }))
  , [metricsHistory]);

  const networkOutData = useMemo(() => 
    metricsHistory.map(m => ({
      timestamp: m.timestamp,
      value: (m.network?.total_io?.bytes_sent || 0) / (1024 * 1024), // Convert to MB
    }))
  , [metricsHistory]);

  const diskReadData = useMemo(() => 
    metricsHistory.map(m => ({
      timestamp: m.timestamp,
      value: (m.disk?.io?.read_bytes || 0) / (1024 * 1024), // Convert to MB
    }))
  , [metricsHistory]);

  const diskWriteData = useMemo(() => 
    metricsHistory.map(m => ({
      timestamp: m.timestamp,
      value: (m.disk?.io?.write_bytes || 0) / (1024 * 1024), // Convert to MB
    }))
  , [metricsHistory]);

  // Current values for circular progress charts
  const currentCpuUsage = currentMetrics?.cpu?.usage_percent || 0;
  const currentMemoryUsage = currentMetrics?.memory?.virtual?.percent || 0;
  const currentSwapUsage = currentMetrics?.memory?.swap?.percent || 0;

  // Calculate disk usage percentage (if available)
  const currentDiskUsage = useMemo(() => {
    if (!currentMetrics?.disk?.partitions?.length) return 0;
    
    const totalSize = currentMetrics.disk.partitions.reduce((sum, p) => sum + p.total, 0);
    const totalUsed = currentMetrics.disk.partitions.reduce((sum, p) => sum + p.used, 0);
    
    return totalSize > 0 ? (totalUsed / totalSize) * 100 : 0;
  }, [currentMetrics]);

  return (
    <Box>
      {/* Current Status Row */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <CircularProgressChart
            title="CPU Usage"
            value={currentCpuUsage}
            unit="%"
            color={theme.palette.error.main}
            size={120}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <CircularProgressChart
            title="Memory Usage"
            value={currentMemoryUsage}
            unit="%"
            color={theme.palette.warning.main}
            size={120}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <CircularProgressChart
            title="Disk Usage"
            value={currentDiskUsage}
            unit="%"
            color={theme.palette.info.main}
            size={120}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <CircularProgressChart
            title="Swap Usage"
            value={currentSwapUsage}
            unit="%"
            color={theme.palette.success.main}
            size={120}
          />
        </Grid>
      </Grid>

      {/* Historical Charts Row */}
      <Grid container spacing={3}>
        {/* CPU Usage Chart */}
        <Grid item xs={12} md={6}>
          <MetricsChart
            title="CPU Usage Over Time"
            data={cpuData}
            unit="%"
            color={theme.palette.error.main}
            height={250}
            maxValue={100}
            minValue={0}
          />
        </Grid>

        {/* Memory Usage Chart */}
        <Grid item xs={12} md={6}>
          <MetricsChart
            title="Memory Usage Over Time"
            data={memoryData}
            unit="%"
            color={theme.palette.warning.main}
            height={250}
            maxValue={100}
            minValue={0}
          />
        </Grid>

        {/* Network Traffic Charts */}
        <Grid item xs={12} md={6}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <MetricsChart
              title="Network In (MB)"
              data={networkInData}
              unit=" MB"
              color={theme.palette.info.main}
              height={120}
              showFill={false}
            />
            <MetricsChart
              title="Network Out (MB)"
              data={networkOutData}
              unit=" MB"
              color={theme.palette.secondary.main}
              height={120}
              showFill={false}
            />
          </Box>
        </Grid>

        {/* Disk I/O Charts */}
        <Grid item xs={12} md={6}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <MetricsChart
              title="Disk Read (MB)"
              data={diskReadData}
              unit=" MB"
              color={theme.palette.success.main}
              height={120}
              showFill={false}
            />
            <MetricsChart
              title="Disk Write (MB)"
              data={diskWriteData}
              unit=" MB"
              color={theme.palette.primary.main}
              height={120}
              showFill={false}
            />
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

export default SystemMetricsGrid;