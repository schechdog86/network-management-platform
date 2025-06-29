import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  Grid,
  Chip,
  IconButton,
  Tooltip,
  Alert,
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  PowerSettingsNew as PowerIcon,
  RestartAlt as RebootIcon,
  Wifi as WakeIcon,
} from '@mui/icons-material';
import { DataGrid, GridColDef, GridRowSelectionModel } from '@mui/x-data-grid';
import { useDeviceStore } from '@/stores/deviceStore';
import { Device } from '@/types';
import LoadingSpinner from '@/components/Common/LoadingSpinner';

const DevicesPage: React.FC = () => {
  const {
    devices,
    isLoading,
    error,
    fetchDevices,
    wakeDevice,
    rebootDevice,
    clearError,
  } = useDeviceStore();

  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    fetchDevices();
  }, [fetchDevices]);

  const handleRefresh = () => {
    fetchDevices();
  };

  const handleWakeDevice = async (deviceId: string) => {
    setActionLoading(`wake_${deviceId}`);
    try {
      await wakeDevice(deviceId);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRebootDevice = async (deviceId: string) => {
    setActionLoading(`reboot_${deviceId}`);
    try {
      await rebootDevice(deviceId);
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusChip = (status: string) => {
    const statusConfig = {
      online: { color: 'success' as const, label: 'Online' },
      offline: { color: 'error' as const, label: 'Offline' },
      unknown: { color: 'warning' as const, label: 'Unknown' },
    };

    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.unknown;
    return <Chip label={config.label} color={config.color} size="small" />;
  };

  const columns: GridColDef[] = [
    {
      field: 'hostname',
      headerName: 'Hostname',
      width: 200,
      renderCell: (params) => (
        <Box>
          <Typography variant="body2" fontWeight="medium">
            {params.row.hostname || 'Unknown'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {params.row.ip_address}
          </Typography>
        </Box>
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => getStatusChip(params.value),
    },
    {
      field: 'device_type',
      headerName: 'Type',
      width: 150,
      renderCell: (params) => (
        <Typography variant="body2">
          {params.value || 'Unknown'}
        </Typography>
      ),
    },
    {
      field: 'vendor',
      headerName: 'Vendor',
      width: 150,
      renderCell: (params) => (
        <Typography variant="body2">
          {params.value || 'Unknown'}
        </Typography>
      ),
    },
    {
      field: 'mac_address',
      headerName: 'MAC Address',
      width: 150,
      renderCell: (params) => (
        <Typography variant="body2" fontFamily="monospace">
          {params.value || 'N/A'}
        </Typography>
      ),
    },
    {
      field: 'capabilities',
      headerName: 'Capabilities',
      width: 150,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {params.row.snmp_enabled && (
            <Chip label="SNMP" size="small" variant="outlined" />
          )}
          {params.row.ssh_enabled && (
            <Chip label="SSH" size="small" variant="outlined" />
          )}
        </Box>
      ),
    },
    {
      field: 'last_seen',
      headerName: 'Last Seen',
      width: 180,
      renderCell: (params) => (
        <Typography variant="body2">
          {params.value ? new Date(params.value).toLocaleString() : 'Never'}
        </Typography>
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      sortable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="Wake on LAN">
            <IconButton
              size="small"
              onClick={() => handleWakeDevice(params.row.id)}
              disabled={actionLoading === `wake_${params.row.id}` || !params.row.mac_address}
            >
              <WakeIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Reboot">
            <IconButton
              size="small"
              onClick={() => handleRebootDevice(params.row.id)}
              disabled={actionLoading === `reboot_${params.row.id}` || params.row.status !== 'online'}
            >
              <RebootIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  if (isLoading && devices.length === 0) {
    return <LoadingSpinner message="Loading devices..." />;
  }

  return (
    <Box>
      {/* Header */}
      <Box mb={3}>
        <Typography variant="h4" component="h1" gutterBottom>
          Device Management
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Monitor and manage network devices
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

      {/* Actions Bar */}
      <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => {
                // TODO: Open add device dialog
                console.log('Add device clicked');
              }}
            >
              Add Device
            </Button>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={handleRefresh}
              disabled={isLoading}
            >
              Refresh
            </Button>
          </Box>
          
          <Box>
            <Typography variant="body2" color="text.secondary">
              {devices.length} devices found
            </Typography>
          </Box>
        </Box>
      </Paper>

      {/* Device Statistics */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" color="primary">
              {devices.length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Total Devices
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" color="success.main">
              {devices.filter(d => d.status === 'online').length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Online
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" color="error.main">
              {devices.filter(d => d.status === 'offline').length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Offline
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" color="warning.main">
              {devices.filter(d => d.status === 'unknown').length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Unknown
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Device Table */}
      <Paper elevation={1}>
        <DataGrid
          rows={devices}
          columns={columns}
          initialState={{
            pagination: {
              paginationModel: { page: 0, pageSize: 25 },
            },
          }}
          pageSizeOptions={[25, 50, 100]}
          checkboxSelection
          disableRowSelectionOnClick
          onRowSelectionModelChange={setSelectedRows}
          loading={isLoading}
          sx={{
            border: 0,
            '& .MuiDataGrid-cell': {
              borderBottom: `1px solid ${(theme) => theme.palette.divider}`,
            },
            '& .MuiDataGrid-columnHeaders': {
              backgroundColor: (theme) => theme.palette.background.default,
              borderBottom: `2px solid ${(theme) => theme.palette.divider}`,
            },
          }}
          getRowHeight={() => 'auto'}
          autoHeight
        />
      </Paper>

      {/* Bulk Actions */}
      {selectedRows.length > 0 && (
        <Paper 
          elevation={2} 
          sx={{ 
            position: 'fixed', 
            bottom: 16, 
            left: '50%', 
            transform: 'translateX(-50%)',
            p: 2,
            display: 'flex',
            gap: 2,
            alignItems: 'center',
            zIndex: 1000
          }}
        >
          <Typography variant="body2">
            {selectedRows.length} devices selected
          </Typography>
          <Button
            variant="outlined"
            size="small"
            startIcon={<WakeIcon />}
            onClick={() => {
              // TODO: Implement bulk wake
              console.log('Bulk wake:', selectedRows);
            }}
          >
            Wake All
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<RebootIcon />}
            onClick={() => {
              // TODO: Implement bulk reboot
              console.log('Bulk reboot:', selectedRows);
            }}
          >
            Reboot All
          </Button>
        </Paper>
      )}
    </Box>
  );
};

export default DevicesPage;