// Runtime configuration for the web interface
// This file is loaded before the React app starts
// and allows for runtime configuration without rebuilding

window._env_ = {
  // API Configuration
  API_URL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  WS_URL: process.env.REACT_APP_WS_URL || 'ws://localhost:8000',
  
  // Feature Flags
  ENABLE_CHAT: process.env.REACT_APP_ENABLE_CHAT !== 'false',
  ENABLE_METRICS: process.env.REACT_APP_ENABLE_METRICS !== 'false',
  ENABLE_AI_FEATURES: process.env.REACT_APP_ENABLE_AI_FEATURES !== 'false',
  
  // Monitoring
  METRICS_REFRESH_INTERVAL: parseInt(process.env.REACT_APP_METRICS_REFRESH_INTERVAL || '5000'),
  
  // Version Info
  VERSION: process.env.REACT_APP_VERSION || '1.0.0',
  BUILD_TIME: process.env.REACT_APP_BUILD_TIME || new Date().toISOString()
};