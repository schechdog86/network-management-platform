import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  IconButton,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Chip,
  Alert,
  Tooltip,
  Tabs,
  Tab,
  Paper,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Snackbar,
  CircularProgress,
  Divider,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  VpnKey as KeyIcon,
  ContentCopy as CopyIcon,
  Refresh as RefreshIcon,
  Computer as ComputerIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Download as DownloadIcon,
  Upload as UploadIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import api from '../../services/api';

interface SSHKey {
  type: string;
  key: string;
  comment: string;
  fingerprint: string;
}

interface SSHKeyList {
  node_id: string;
  keys: SSHKey[];
  total: number;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`ssh-tabpanel-${index}`}
      aria-labelledby={`ssh-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

interface SSHKeyManagerProps {
  nodeId: string;
  nodeName?: string;
}

const SSHKeyManager: React.FC<SSHKeyManagerProps> = ({ nodeId, nodeName }) => {
  const [keys, setKeys] = useState<SSHKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [tabValue, setTabValue] = useState(0);
  const [generateDialogOpen, setGenerateDialogOpen] = useState(false);
  const [addKeyDialogOpen, setAddKeyDialogOpen] = useState(false);
  const [testConnectionDialogOpen, setTestConnectionDialogOpen] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  // Generate key form
  const [keyType, setKeyType] = useState('ed25519');
  const [keyComment, setKeyComment] = useState('');
  const [generatedKeys, setGeneratedKeys] = useState<{ public: string; private: string } | null>(null);

  // Add key form
  const [publicKeyToAdd, setPublicKeyToAdd] = useState('');
  const [addKeyComment, setAddKeyComment] = useState('');

  // Test connection form
  const [testHostname, setTestHostname] = useState('');
  const [testUsername, setTestUsername] = useState('');
  const [testPort, setTestPort] = useState('22');
  const [connectionResult, setConnectionResult] = useState<any>(null);

  useEffect(() => {
    fetchKeys();
  }, [nodeId]);

  const fetchKeys = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/api/v1/ssh-keys/list/${nodeId}`);
      setKeys(response.data.keys);
    } catch (error) {
      console.error('Error fetching SSH keys:', error);
      showSnackbar('Failed to fetch SSH keys', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateKey = async () => {
    try {
      const response = await api.post('/api/v1/ssh-keys/generate', {
        node_id: nodeId,
        key_type: keyType,
        comment: keyComment || `${nodeName || nodeId}@network-platform`,
        include_private: true,
      });

      setGeneratedKeys({
        public: response.data.public_key,
        private: response.data.private_key,
      });

      showSnackbar('SSH key pair generated successfully', 'success');
      fetchKeys();
    } catch (error) {
      console.error('Error generating SSH key:', error);
      showSnackbar('Failed to generate SSH key', 'error');
    }
  };

  const handleAddKey = async () => {
    try {
      await api.post('/api/v1/ssh-keys/add', {
        node_id: nodeId,
        public_key: publicKeyToAdd,
        comment: addKeyComment,
      });

      showSnackbar('SSH key added successfully', 'success');
      setAddKeyDialogOpen(false);
      setPublicKeyToAdd('');
      setAddKeyComment('');
      fetchKeys();
    } catch (error) {
      console.error('Error adding SSH key:', error);
      showSnackbar('Failed to add SSH key', 'error');
    }
  };

  const handleDeleteKey = async (fingerprint: string) => {
    if (!window.confirm('Are you sure you want to remove this SSH key?')) {
      return;
    }

    try {
      await api.delete(`/api/v1/ssh-keys/remove/${nodeId}`, {
        params: { fingerprint },
      });

      showSnackbar('SSH key removed successfully', 'success');
      fetchKeys();
    } catch (error) {
      console.error('Error removing SSH key:', error);
      showSnackbar('Failed to remove SSH key', 'error');
    }
  };

  const handleTestConnection = async () => {
    try {
      setConnectionResult(null);
      const response = await api.post('/api/v1/ssh-keys/test-connection', {
        hostname: testHostname,
        port: parseInt(testPort),
        username: testUsername || undefined,
        node_id: nodeId,
      });

      setConnectionResult(response.data);
    } catch (error) {
      console.error('Error testing connection:', error);
      showSnackbar('Failed to test SSH connection', 'error');
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    showSnackbar('Copied to clipboard', 'success');
  };

  const downloadKey = (content: string, filename: string) => {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const showSnackbar = (message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity });
  };

  const getKeyIcon = (keyType: string) => {
    switch (keyType) {
      case 'ssh-ed25519':
        return <Chip label="Ed25519" size="small" color="primary" />;
      case 'ssh-rsa':
        return <Chip label="RSA" size="small" color="secondary" />;
      case 'ecdsa-sha2-nistp256':
        return <Chip label="ECDSA" size="small" color="info" />;
      default:
        return <Chip label={keyType} size="small" />;
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={400}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">
              <KeyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              SSH Key Management - {nodeName || nodeId}
            </Typography>
            <Box>
              <Tooltip title="Refresh">
                <IconButton onClick={fetchKeys}>
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => setTabValue(0)}
                sx={{ ml: 1 }}
              >
                Manage Keys
              </Button>
            </Box>
          </Box>

          <Paper variant="outlined">
            <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
              <Tab label="Authorized Keys" />
              <Tab label="Generate Key" />
              <Tab label="Add Key" />
              <Tab label="Test Connection" />
            </Tabs>

            <TabPanel value={tabValue} index={0}>
              {keys.length === 0 ? (
                <Alert severity="info">
                  No SSH keys found for this node. Generate or add a key to get started.
                </Alert>
              ) : (
                <List>
                  {keys.map((key, index) => (
                    <React.Fragment key={key.fingerprint}>
                      <ListItem>
                        <ListItemText
                          primary={
                            <Box display="flex" alignItems="center" gap={1}>
                              {getKeyIcon(key.type)}
                              <Typography variant="body2">{key.comment || 'No comment'}</Typography>
                            </Box>
                          }
                          secondary={
                            <Box>
                              <Typography variant="caption" component="div">
                                Fingerprint: {key.fingerprint}
                              </Typography>
                              <Typography variant="caption" component="div" sx={{ 
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                maxWidth: '600px'
                              }}>
                                {key.type} {key.key.substring(0, 50)}...
                              </Typography>
                            </Box>
                          }
                        />
                        <ListItemSecondaryAction>
                          <Tooltip title="Copy public key">
                            <IconButton
                              edge="end"
                              onClick={() => copyToClipboard(`${key.type} ${key.key} ${key.comment}`)}
                            >
                              <CopyIcon />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Remove key">
                            <IconButton
                              edge="end"
                              onClick={() => handleDeleteKey(key.fingerprint)}
                              color="error"
                            >
                              <DeleteIcon />
                            </IconButton>
                          </Tooltip>
                        </ListItemSecondaryAction>
                      </ListItem>
                      {index < keys.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
              )}
            </TabPanel>

            <TabPanel value={tabValue} index={1}>
              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <Typography variant="body2" gutterBottom>
                    Generate a new SSH key pair for this node
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth>
                    <InputLabel>Key Type</InputLabel>
                    <Select
                      value={keyType}
                      onChange={(e) => setKeyType(e.target.value)}
                      label="Key Type"
                    >
                      <MenuItem value="ed25519">Ed25519 (Recommended)</MenuItem>
                      <MenuItem value="rsa">RSA</MenuItem>
                      <MenuItem value="ecdsa">ECDSA</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Comment (optional)"
                    value={keyComment}
                    onChange={(e) => setKeyComment(e.target.value)}
                    placeholder="user@hostname"
                  />
                </Grid>
                <Grid item xs={12}>
                  <Button
                    variant="contained"
                    onClick={handleGenerateKey}
                    startIcon={<KeyIcon />}
                  >
                    Generate Key Pair
                  </Button>
                </Grid>

                {generatedKeys && (
                  <Grid item xs={12}>
                    <Alert severity="success" sx={{ mb: 2 }}>
                      SSH key pair generated successfully!
                    </Alert>
                    <Box mb={2}>
                      <Typography variant="subtitle2" gutterBottom>
                        Public Key:
                      </Typography>
                      <Paper variant="outlined" sx={{ p: 2, mb: 1 }}>
                        <Typography
                          variant="body2"
                          sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}
                        >
                          {generatedKeys.public}
                        </Typography>
                      </Paper>
                      <Button
                        size="small"
                        startIcon={<CopyIcon />}
                        onClick={() => copyToClipboard(generatedKeys.public)}
                      >
                        Copy Public Key
                      </Button>
                    </Box>
                    <Box>
                      <Typography variant="subtitle2" gutterBottom>
                        Private Key:
                      </Typography>
                      <Alert severity="warning" sx={{ mb: 1 }}>
                        Save this private key securely. It won't be shown again.
                      </Alert>
                      <Button
                        variant="outlined"
                        startIcon={<DownloadIcon />}
                        onClick={() => downloadKey(generatedKeys.private, `${nodeId}_ed25519`)}
                      >
                        Download Private Key
                      </Button>
                    </Box>
                  </Grid>
                )}
              </Grid>
            </TabPanel>

            <TabPanel value={tabValue} index={2}>
              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <Typography variant="body2" gutterBottom>
                    Add an existing SSH public key to this node's authorized keys
                  </Typography>
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    multiline
                    rows={4}
                    label="SSH Public Key"
                    value={publicKeyToAdd}
                    onChange={(e) => setPublicKeyToAdd(e.target.value)}
                    placeholder="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... user@hostname"
                  />
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Comment (optional)"
                    value={addKeyComment}
                    onChange={(e) => setAddKeyComment(e.target.value)}
                    placeholder="user@hostname"
                  />
                </Grid>
                <Grid item xs={12}>
                  <Button
                    variant="contained"
                    onClick={handleAddKey}
                    startIcon={<UploadIcon />}
                    disabled={!publicKeyToAdd.trim()}
                  >
                    Add Public Key
                  </Button>
                </Grid>
              </Grid>
            </TabPanel>

            <TabPanel value={tabValue} index={3}>
              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <Typography variant="body2" gutterBottom>
                    Test SSH connection from this node to a remote host
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Hostname or IP"
                    value={testHostname}
                    onChange={(e) => setTestHostname(e.target.value)}
                    placeholder="192.168.1.100"
                  />
                </Grid>
                <Grid item xs={12} sm={3}>
                  <TextField
                    fullWidth
                    label="Username (optional)"
                    value={testUsername}
                    onChange={(e) => setTestUsername(e.target.value)}
                    placeholder="root"
                  />
                </Grid>
                <Grid item xs={12} sm={3}>
                  <TextField
                    fullWidth
                    label="Port"
                    type="number"
                    value={testPort}
                    onChange={(e) => setTestPort(e.target.value)}
                  />
                </Grid>
                <Grid item xs={12}>
                  <Button
                    variant="contained"
                    onClick={handleTestConnection}
                    startIcon={<ComputerIcon />}
                    disabled={!testHostname.trim()}
                  >
                    Test Connection
                  </Button>
                </Grid>

                {connectionResult && (
                  <Grid item xs={12}>
                    <Alert
                      severity={connectionResult.status === 'authenticated' ? 'success' : 
                               connectionResult.status === 'error' ? 'error' : 'warning'}
                      icon={connectionResult.status === 'authenticated' ? <CheckIcon /> : 
                            connectionResult.status === 'error' ? <ErrorIcon /> : undefined}
                    >
                      <Typography variant="subtitle2">
                        Connection Status: {connectionResult.status}
                      </Typography>
                      {connectionResult.server_version && (
                        <Typography variant="body2">
                          Server: {connectionResult.server_version}
                        </Typography>
                      )}
                      {connectionResult.error && (
                        <Typography variant="body2" color="error">
                          Error: {connectionResult.error}
                        </Typography>
                      )}
                    </Alert>
                  </Grid>
                )}
              </Grid>
            </TabPanel>
          </Paper>
        </CardContent>
      </Card>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        message={snackbar.message}
      />
    </Box>
  );
};

export default SSHKeyManager;