import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Tabs,
  Tab,
  Paper,
} from '@mui/material';
import { useDeviceStore } from '../stores/deviceStore';
import {
  FleetHealthDashboard,
  MaintenanceSchedule,
} from '../components/PredictiveMaintenance/HealthDashboard';
import LoadingSpinner from '@/components/Common/LoadingSpinner';

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
      id={`predictive-tabpanel-${index}`}
      aria-labelledby={`predictive-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ py: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const PredictiveMaintenancePage: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [initialLoading, setInitialLoading] = useState(true);
  const { devices, fetchDevices, isLoading } = useDeviceStore();
  const [deviceIds, setDeviceIds] = useState<string[]>([]);

  useEffect(() => {
    const loadData = async () => {
      try {
        await fetchDevices();
      } finally {
        setInitialLoading(false);
      }
    };
    loadData();
  }, [fetchDevices]);

  useEffect(() => {
    // Extract device IDs when devices are loaded
    if (devices.length > 0) {
      setDeviceIds(devices.map(d => d.id));
    }
  }, [devices]);

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  if (initialLoading || isLoading) {
    return <LoadingSpinner message="Loading predictive maintenance data..." />;
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Predictive Maintenance
      </Typography>
      
      <Paper sx={{ width: '100%', mb: 2 }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          indicatorColor="primary"
          textColor="primary"
          variant="fullWidth"
        >
          <Tab label="Fleet Health Overview" />
          <Tab label="Maintenance Scheduling" />
        </Tabs>
      </Paper>

      <TabPanel value={tabValue} index={0}>
        <FleetHealthDashboard deviceIds={deviceIds} />
      </TabPanel>

      <TabPanel value={tabValue} index={1}>
        <MaintenanceSchedule deviceIds={deviceIds} />
      </TabPanel>
    </Box>
  );
};

export default PredictiveMaintenancePage;