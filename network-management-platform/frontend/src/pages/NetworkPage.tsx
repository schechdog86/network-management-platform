import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  TextField,
  Grid,
  Alert,
  Chip,
  LinearProgress,
} from '@mui/material';
import {
  Search as SearchIcon,
  NetworkCheck as NetworkIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import LoadingSpinner from '@/components/Common/LoadingSpinner';

const NetworkPage: React.FC = () => {
  const [subnet, setSubnet] = useState('192.168.1.0/24');
  const [scanType, setScanType] = useState('ping');
  const [isScanning, setIsScanning] = useState(false);
  const [scanResults, setScanResults] = useState<any[]>([]);
  const [scanProgress, setScanProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const handleStartScan = async () => {
    if (!subnet.trim()) {
      setError('Please enter a valid subnet');
      return;
    }

    setIsScanning(true);
    setError(null);
    setScanResults([]);
    setScanProgress(0);

    try {
      // Simulate network scan progress
      const progressInterval = setInterval(() => {
        setScanProgress(prev => {
          if (prev >= 100) {
            clearInterval(progressInterval);
            return 100;
          }
          return prev + 10;
        });
      }, 500);

      // Simulate scan completion after 5 seconds
      setTimeout(() => {
        clearInterval(progressInterval);
        setScanProgress(100);
        setIsScanning(false);
        
        // Mock scan results
        setScanResults([
          {
            ip: '192.168.1.1',
            hostname: 'router.local',
            status: 'online',
            mac: '00:11:22:33:44:55',
            vendor: 'Cisco',
            ports: [22, 80, 443],
          },
          {
            ip: '192.168.1.10',
            hostname: 'server-01.local',
            status: 'online',
            mac: 'AA:BB:CC:DD:EE:FF',
            vendor: 'Dell',
            ports: [22, 80, 443, 3306],
          },
          {
            ip: '192.168.1.20',
            hostname: 'workstation-01',
            status: 'offline',
            mac: '11:22:33:44:55:66',
            vendor: 'HP',
            ports: [],
          },
        ]);
      }, 5000);

    } catch (err: any) {
      setError(err.message || 'Network scan failed');
      setIsScanning(false);
      setScanProgress(0);
    }
  };

  const getScanTypeOptions = () => [
    { value: 'ping', label: 'Ping Scan (Fast)' },
    { value: 'tcp', label: 'TCP Scan (Common Ports)' },
    { value: 'comprehensive', label: 'Comprehensive Scan (Slow)' },
  ];

  const getStatusChip = (status: string) => {
    const statusConfig = {
      online: { color: 'success' as const, label: 'Online' },
      offline: { color: 'error' as const, label: 'Offline' },
    };

    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.offline;
    return <Chip label={config.label} color={config.color} size="small" />;
  };

  return (
    <Box>
      {/* Header */}
      <Box mb={3}>
        <Typography variant="h4" component="h1" gutterBottom>
          Network Discovery
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Scan and discover devices on your network
        </Typography>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert 
          severity="error" 
          onClose={() => setError(null)}
          sx={{ mb: 3 }}
        >
          {error}
        </Alert>
      )}

      {/* Scan Configuration */}
      <Paper elevation={1} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Scan Configuration
        </Typography>
        
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              label="Subnet to Scan"
              value={subnet}
              onChange={(e) => setSubnet(e.target.value)}
              placeholder="192.168.1.0/24"
              disabled={isScanning}
              helperText="Enter network range in CIDR notation"
            />
          </Grid>
          
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              select
              label="Scan Type"
              value={scanType}
              onChange={(e) => setScanType(e.target.value)}
              disabled={isScanning}
              SelectProps={{
                native: true,
              }}
            >
              {getScanTypeOptions().map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </TextField>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Button
              variant="contained"
              size="large"
              startIcon={isScanning ? <RefreshIcon /> : <SearchIcon />}
              onClick={handleStartScan}
              disabled={isScanning || !subnet.trim()}
              fullWidth
            >
              {isScanning ? 'Scanning...' : 'Start Scan'}
            </Button>
          </Grid>
        </Grid>

        {/* Progress Bar */}
        {isScanning && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Scan Progress: {scanProgress}%
            </Typography>
            <LinearProgress 
              variant="determinate" 
              value={scanProgress}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
        )}
      </Paper>

      {/* Scan Results */}
      {scanResults.length > 0 && (
        <Paper elevation={1} sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">
              Scan Results
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {scanResults.length} devices found
            </Typography>
          </Box>

          <Grid container spacing={2}>
            {scanResults.map((device, index) => (
              <Grid item xs={12} md={6} lg={4} key={index}>
                <Paper 
                  variant="outlined" 
                  sx={{ 
                    p: 2,
                    '&:hover': {
                      boxShadow: 2,
                    }
                  }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="h6" component="div">
                      {device.hostname || device.ip}
                    </Typography>
                    {getStatusChip(device.status)}
                  </Box>

                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    IP: {device.ip}
                  </Typography>

                  {device.mac && (
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      MAC: {device.mac}
                    </Typography>
                  )}

                  {device.vendor && (
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Vendor: {device.vendor}
                    </Typography>
                  )}

                  {device.ports && device.ports.length > 0 && (
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Open Ports:
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {device.ports.map((port: number) => (
                          <Chip 
                            key={port}
                            label={port}
                            size="small"
                            variant="outlined"
                          />
                        ))}
                      </Box>
                    </Box>
                  )}

                  <Box sx={{ mt: 2 }}>
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={() => {
                        // TODO: Add device to management
                        console.log('Add device:', device);
                      }}
                    >
                      Add to Management
                    </Button>
                  </Box>
                </Paper>
              </Grid>
            ))}
          </Grid>
        </Paper>
      )}

      {/* Empty State */}
      {!isScanning && scanResults.length === 0 && (
        <Paper 
          elevation={0} 
          sx={{ 
            p: 6, 
            textAlign: 'center',
            bgcolor: 'background.default'
          }}
        >
          <NetworkIcon 
            sx={{ 
              fontSize: 64, 
              color: 'text.secondary',
              mb: 2
            }} 
          />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No scan results yet
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Configure your scan parameters and click "Start Scan" to discover devices on your network
          </Typography>
        </Paper>
      )}
    </Box>
  );
};

export default NetworkPage;