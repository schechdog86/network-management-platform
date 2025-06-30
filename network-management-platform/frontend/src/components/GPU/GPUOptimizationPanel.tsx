import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Slider,
  Switch,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  FormControlLabel,
  Alert,
  AlertTitle,
  Chip,
  Divider,
  LinearProgress,
  Tooltip,
  IconButton,
  Collapse,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Paper,
  CircularProgress,
} from '@mui/material';
import {
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  SettingsApplications as SettingsIcon,
  TrendingUp as PerformanceIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  RestartAlt as ResetIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';
import api from '../../services/api';
import { useSnackbar } from 'notistack';

interface GPUSettings {
  profile: string;
  batch_size_multiplier: number;
  memory_fraction: number;
  mixed_precision: boolean;
  xla_jit: boolean;
  cudnn_benchmark: boolean;
  tensorrt_optimization: boolean;
  dynamic_batching: boolean;
  gradient_accumulation_steps: number;
  gradient_checkpointing: boolean;
  power_limit?: number;
  gpu_clock?: number;
  memory_clock?: number;
}

interface Recommendation {
  setting: string;
  current: any;
  recommended: any;
  reason: string;
}

const GPUOptimizationPanel: React.FC = () => {
  const { enqueueSnackbar } = useSnackbar();
  const [settings, setSettings] = useState<GPUSettings | null>(null);
  const [profiles, setProfiles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [workloadType, setWorkloadType] = useState<'inference' | 'training'>('inference');

  useEffect(() => {
    fetchSettings();
  }, []);

  useEffect(() => {
    if (settings) {
      fetchRecommendations();
    }
  }, [workloadType]);

  const fetchSettings = async () => {
    try {
      const response = await api.get('/api/v1/gpu-optimization/settings');
      setSettings(response.data.settings);
      setProfiles(response.data.profiles);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching GPU settings:', error);
      enqueueSnackbar('Failed to load GPU settings', { variant: 'error' });
      setLoading(false);
    }
  };

  const fetchRecommendations = async () => {
    try {
      const response = await api.get(`/api/v1/gpu-optimization/recommendations/${workloadType}`);
      setRecommendations(response.data.recommendations);
    } catch (error) {
      console.error('Error fetching recommendations:', error);
    }
  };

  const applyProfile = async (profile: string) => {
    setSaving(true);
    try {
      const response = await api.post(`/api/v1/gpu-optimization/profile/${profile}`);
      setSettings(response.data.settings);
      enqueueSnackbar(`Applied ${profile} GPU profile`, { variant: 'success' });
    } catch (error) {
      console.error('Error applying profile:', error);
      enqueueSnackbar('Failed to apply GPU profile', { variant: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const updateSettings = async (updates: Partial<GPUSettings>) => {
    setSaving(true);
    try {
      const response = await api.patch('/api/v1/gpu-optimization/settings', updates);
      setSettings(response.data.settings);
      enqueueSnackbar('GPU settings updated', { variant: 'success' });
    } catch (error) {
      console.error('Error updating settings:', error);
      enqueueSnackbar('Failed to update GPU settings', { variant: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const resetSettings = async () => {
    setSaving(true);
    try {
      const response = await api.post('/api/v1/gpu-optimization/reset');
      setSettings(response.data.settings);
      enqueueSnackbar('GPU settings reset to defaults', { variant: 'info' });
    } catch (error) {
      console.error('Error resetting settings:', error);
      enqueueSnackbar('Failed to reset GPU settings', { variant: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const getProfileColor = (profile: string) => {
    switch (profile) {
      case 'conservative':
        return 'info';
      case 'balanced':
        return 'primary';
      case 'aggressive':
        return 'warning';
      case 'maximum':
        return 'error';
      default:
        return 'default';
    }
  };

  const getProfileDescription = (profile: string) => {
    switch (profile) {
      case 'conservative':
        return '50-60% GPU utilization - Stable but slower';
      case 'balanced':
        return '70-80% GPU utilization - Good balance';
      case 'aggressive':
        return '85-95% GPU utilization - Faster, less stable';
      case 'maximum':
        return '95-100% GPU utilization - Maximum performance';
      default:
        return '';
    }
  };

  if (loading || !settings) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        GPU Optimization Settings
      </Typography>

      {/* Profile Selection */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Optimization Profile
          </Typography>
          <Grid container spacing={2}>
            {profiles.map((profile) => (
              <Grid item xs={12} sm={6} md={3} key={profile}>
                <Paper
                  elevation={settings.profile === profile ? 3 : 1}
                  sx={{
                    p: 2,
                    cursor: 'pointer',
                    border: settings.profile === profile ? 2 : 0,
                    borderColor: 'primary.main',
                    '&:hover': { elevation: 3 },
                  }}
                  onClick={() => applyProfile(profile)}
                >
                  <Box display="flex" alignItems="center" mb={1}>
                    <Chip
                      label={profile.toUpperCase()}
                      color={getProfileColor(profile) as any}
                      size="small"
                    />
                    {settings.profile === profile && (
                      <CheckCircleIcon color="primary" sx={{ ml: 'auto' }} />
                    )}
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    {getProfileDescription(profile)}
                  </Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>
        </CardContent>
      </Card>

      {/* Quick Settings */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">Quick Settings</Typography>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Workload</InputLabel>
              <Select
                value={workloadType}
                onChange={(e) => setWorkloadType(e.target.value as 'inference' | 'training')}
                label="Workload"
              >
                <MenuItem value="inference">Inference</MenuItem>
                <MenuItem value="training">Training</MenuItem>
              </Select>
            </FormControl>
          </Box>

          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Typography gutterBottom>
                Batch Size Multiplier: {settings.batch_size_multiplier}x
              </Typography>
              <Slider
                value={settings.batch_size_multiplier}
                onChange={(e, value) => setSettings({ ...settings, batch_size_multiplier: value as number })}
                onChangeCommitted={(e, value) => updateSettings({ batch_size_multiplier: value as number })}
                min={0.5}
                max={3}
                step={0.1}
                marks={[
                  { value: 0.5, label: '0.5x' },
                  { value: 1, label: '1x' },
                  { value: 2, label: '2x' },
                  { value: 3, label: '3x' },
                ]}
                valueLabelDisplay="auto"
                disabled={saving}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography gutterBottom>
                GPU Memory Usage: {(settings.memory_fraction * 100).toFixed(0)}%
              </Typography>
              <Slider
                value={settings.memory_fraction}
                onChange={(e, value) => setSettings({ ...settings, memory_fraction: value as number })}
                onChangeCommitted={(e, value) => updateSettings({ memory_fraction: value as number })}
                min={0.5}
                max={0.95}
                step={0.05}
                marks={[
                  { value: 0.5, label: '50%' },
                  { value: 0.7, label: '70%' },
                  { value: 0.9, label: '90%' },
                ]}
                valueLabelDisplay="auto"
                valueLabelFormat={(value) => `${(value * 100).toFixed(0)}%`}
                disabled={saving}
              />
            </Grid>

            <Grid item xs={12}>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={3}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={settings.mixed_precision}
                        onChange={(e) => updateSettings({ mixed_precision: e.target.checked })}
                        disabled={saving}
                      />
                    }
                    label="Mixed Precision"
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={settings.xla_jit}
                        onChange={(e) => updateSettings({ xla_jit: e.target.checked })}
                        disabled={saving}
                      />
                    }
                    label="XLA JIT"
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={settings.cudnn_benchmark}
                        onChange={(e) => updateSettings({ cudnn_benchmark: e.target.checked })}
                        disabled={saving}
                      />
                    }
                    label="CuDNN Benchmark"
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={settings.tensorrt_optimization}
                        onChange={(e) => updateSettings({ tensorrt_optimization: e.target.checked })}
                        disabled={saving}
                      />
                    }
                    label="TensorRT"
                  />
                </Grid>
              </Grid>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Optimization Recommendations for {workloadType}
            </Typography>
            <List>
              {recommendations.map((rec, index) => (
                <ListItem key={index}>
                  <ListItemIcon>
                    <InfoIcon color="info" />
                  </ListItemIcon>
                  <ListItemText
                    primary={rec.setting.replace(/_/g, ' ').toUpperCase()}
                    secondary={
                      <Box>
                        <Typography variant="body2">{rec.reason}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          Current: {JSON.stringify(rec.current)} → Recommended: {JSON.stringify(rec.recommended)}
                        </Typography>
                      </Box>
                    }
                  />
                  <Button
                    size="small"
                    onClick={() => updateSettings({ [rec.setting]: rec.recommended })}
                    disabled={saving}
                  >
                    Apply
                  </Button>
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      )}

      {/* Advanced Settings */}
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">Advanced Settings</Typography>
            <IconButton onClick={() => setShowAdvanced(!showAdvanced)}>
              {showAdvanced ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          </Box>

          <Collapse in={showAdvanced}>
            <Box mt={2}>
              <Grid container spacing={3}>
                <Grid item xs={12} md={4}>
                  <Typography gutterBottom>
                    Gradient Accumulation Steps: {settings.gradient_accumulation_steps}
                  </Typography>
                  <Slider
                    value={settings.gradient_accumulation_steps}
                    onChange={(e, value) => setSettings({ ...settings, gradient_accumulation_steps: value as number })}
                    onChangeCommitted={(e, value) => updateSettings({ gradient_accumulation_steps: value as number })}
                    min={1}
                    max={16}
                    marks
                    valueLabelDisplay="auto"
                    disabled={saving}
                  />
                </Grid>

                <Grid item xs={12} md={4}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={settings.gradient_checkpointing}
                        onChange={(e) => updateSettings({ gradient_checkpointing: e.target.checked })}
                        disabled={saving}
                      />
                    }
                    label="Gradient Checkpointing"
                  />
                </Grid>

                <Grid item xs={12} md={4}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={settings.dynamic_batching}
                        onChange={(e) => updateSettings({ dynamic_batching: e.target.checked })}
                        disabled={saving}
                      />
                    }
                    label="Dynamic Batching"
                  />
                </Grid>
              </Grid>

              <Divider sx={{ my: 2 }} />

              <Alert severity="warning" sx={{ mt: 2 }}>
                <AlertTitle>Power Settings (Requires Admin)</AlertTitle>
                These settings directly control GPU hardware and require administrator privileges.
              </Alert>
            </Box>
          </Collapse>
        </CardContent>

        <Box p={2} display="flex" justifyContent="flex-end">
          <Button
            startIcon={<ResetIcon />}
            onClick={resetSettings}
            disabled={saving}
          >
            Reset to Defaults
          </Button>
        </Box>
      </Card>

      {saving && <LinearProgress sx={{ mt: 2 }} />}
    </Box>
  );
};

export default GPUOptimizationPanel;