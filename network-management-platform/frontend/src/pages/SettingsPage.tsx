import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  TextField,
  Button,
  Switch,
  FormControlLabel,
  Alert,
  Chip,
} from '@mui/material';
import {
  Save as SaveIcon,
  Refresh as RefreshIcon,
  Security as SecurityIcon,
  NetworkCheck as NetworkIcon,
  Storage as StorageIcon,
} from '@mui/icons-material';
import { useAuthStore } from '@/stores/authStore';

const SettingsPage: React.FC = () => {
  const { user } = useAuthStore();
  const [settings, setSettings] = useState({
    // Network Settings
    defaultScanTimeout: 30,
    maxConcurrentScans: 10,
    snmpCommunity: 'public',
    snmpTimeout: 5,
    
    // System Settings
    metricsRetentionDays: 30,
    logLevel: 'INFO',
    enableNotifications: true,
    enableAutoBackup: false,
    
    // Security Settings
    sessionTimeout: 30,
    enableTwoFactor: false,
    allowRemoteAccess: true,
    
    // Backup Settings
    backupRetentionDays: 90,
    backupInterval: 24,
    enableCompression: true,
  });

  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');

  const handleSettingChange = (key: string, value: string | number | boolean) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleSaveSettings = async () => {
    setSaveStatus('saving');
    
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      setSaveStatus('success');
      
      // Reset status after 3 seconds
      setTimeout(() => setSaveStatus('idle'), 3000);
    } catch (error) {
      setSaveStatus('error');
      setTimeout(() => setSaveStatus('idle'), 3000);
    }
  };

  const handleResetSettings = () => {
    // Reset to default values
    setSettings({
      defaultScanTimeout: 30,
      maxConcurrentScans: 10,
      snmpCommunity: 'public',
      snmpTimeout: 5,
      metricsRetentionDays: 30,
      logLevel: 'INFO',
      enableNotifications: true,
      enableAutoBackup: false,
      sessionTimeout: 30,
      enableTwoFactor: false,
      allowRemoteAccess: true,
      backupRetentionDays: 90,
      backupInterval: 24,
      enableCompression: true,
    });
  };

  return (
    <Box>
      {/* Header */}
      <Box mb={3}>
        <Typography variant="h4" component="h1" gutterBottom>
          Settings
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Configure system preferences and options
        </Typography>
      </Box>

      {/* Save Status Alert */}
      {saveStatus === 'success' && (
        <Alert severity="success" sx={{ mb: 3 }}>
          Settings saved successfully
        </Alert>
      )}
      {saveStatus === 'error' && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to save settings. Please try again.
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* User Profile */}
        <Grid item xs={12}>
          <Paper elevation={1} sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <SecurityIcon sx={{ mr: 1 }} />
              <Typography variant="h6">User Profile</Typography>
            </Box>
            
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Username"
                  value={user?.username || ''}
                  disabled
                  helperText="Username cannot be changed"
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Email"
                  value={user?.email || ''}
                  disabled
                  helperText="Contact administrator to change email"
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Role"
                  value={user?.role || ''}
                  disabled
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Account Status
                  </Typography>
                  <Chip 
                    label={user?.is_active ? 'Active' : 'Inactive'} 
                    color={user?.is_active ? 'success' : 'error'}
                    size="small"
                  />
                </Box>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Network Settings */}
        <Grid item xs={12} md={6}>
          <Paper elevation={1} sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <NetworkIcon sx={{ mr: 1 }} />
              <Typography variant="h6">Network Settings</Typography>
            </Box>
            
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <TextField
                fullWidth
                label="Default Scan Timeout (seconds)"
                type="number"
                value={settings.defaultScanTimeout}
                onChange={(e) => handleSettingChange('defaultScanTimeout', Number(e.target.value))}
                inputProps={{ min: 5, max: 300 }}
              />
              
              <TextField
                fullWidth
                label="Max Concurrent Scans"
                type="number"
                value={settings.maxConcurrentScans}
                onChange={(e) => handleSettingChange('maxConcurrentScans', Number(e.target.value))}
                inputProps={{ min: 1, max: 50 }}
              />
              
              <TextField
                fullWidth
                label="Default SNMP Community"
                value={settings.snmpCommunity}
                onChange={(e) => handleSettingChange('snmpCommunity', e.target.value)}
              />
              
              <TextField
                fullWidth
                label="SNMP Timeout (seconds)"
                type="number"
                value={settings.snmpTimeout}
                onChange={(e) => handleSettingChange('snmpTimeout', Number(e.target.value))}
                inputProps={{ min: 1, max: 30 }}
              />
            </Box>
          </Paper>
        </Grid>

        {/* System Settings */}
        <Grid item xs={12} md={6}>
          <Paper elevation={1} sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              System Settings
            </Typography>
            
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <TextField
                fullWidth
                label="Metrics Retention (days)"
                type="number"
                value={settings.metricsRetentionDays}
                onChange={(e) => handleSettingChange('metricsRetentionDays', Number(e.target.value))}
                inputProps={{ min: 1, max: 365 }}
              />
              
              <TextField
                fullWidth
                select
                label="Log Level"
                value={settings.logLevel}
                onChange={(e) => handleSettingChange('logLevel', e.target.value)}
                SelectProps={{ native: true }}
              >
                <option value="DEBUG">Debug</option>
                <option value="INFO">Info</option>
                <option value="WARNING">Warning</option>
                <option value="ERROR">Error</option>
              </TextField>
              
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.enableNotifications}
                    onChange={(e) => handleSettingChange('enableNotifications', e.target.checked)}
                  />
                }
                label="Enable Notifications"
              />
              
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.enableAutoBackup}
                    onChange={(e) => handleSettingChange('enableAutoBackup', e.target.checked)}
                  />
                }
                label="Enable Auto Backup"
              />
            </Box>
          </Paper>
        </Grid>

        {/* Security Settings */}
        <Grid item xs={12} md={6}>
          <Paper elevation={1} sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <SecurityIcon sx={{ mr: 1 }} />
              <Typography variant="h6">Security Settings</Typography>
            </Box>
            
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <TextField
                fullWidth
                label="Session Timeout (minutes)"
                type="number"
                value={settings.sessionTimeout}
                onChange={(e) => handleSettingChange('sessionTimeout', Number(e.target.value))}
                inputProps={{ min: 5, max: 480 }}
              />
              
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.enableTwoFactor}
                    onChange={(e) => handleSettingChange('enableTwoFactor', e.target.checked)}
                  />
                }
                label="Enable Two-Factor Authentication"
              />
              
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.allowRemoteAccess}
                    onChange={(e) => handleSettingChange('allowRemoteAccess', e.target.checked)}
                  />
                }
                label="Allow Remote Access"
              />
            </Box>
          </Paper>
        </Grid>

        {/* Backup Settings */}
        <Grid item xs={12} md={6}>
          <Paper elevation={1} sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <StorageIcon sx={{ mr: 1 }} />
              <Typography variant="h6">Backup Settings</Typography>
            </Box>
            
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <TextField
                fullWidth
                label="Backup Retention (days)"
                type="number"
                value={settings.backupRetentionDays}
                onChange={(e) => handleSettingChange('backupRetentionDays', Number(e.target.value))}
                inputProps={{ min: 1, max: 365 }}
              />
              
              <TextField
                fullWidth
                label="Backup Interval (hours)"
                type="number"
                value={settings.backupInterval}
                onChange={(e) => handleSettingChange('backupInterval', Number(e.target.value))}
                inputProps={{ min: 1, max: 168 }}
              />
              
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.enableCompression}
                    onChange={(e) => handleSettingChange('enableCompression', e.target.checked)}
                  />
                }
                label="Enable Compression"
              />
            </Box>
          </Paper>
        </Grid>

        {/* Actions */}
        <Grid item xs={12}>
          <Paper elevation={1} sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Actions
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                startIcon={<SaveIcon />}
                onClick={handleSaveSettings}
                disabled={saveStatus === 'saving'}
              >
                {saveStatus === 'saving' ? 'Saving...' : 'Save Settings'}
              </Button>
              
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={handleResetSettings}
                disabled={saveStatus === 'saving'}
              >
                Reset to Defaults
              </Button>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default SettingsPage;