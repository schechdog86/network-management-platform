import React, { useState } from 'react';
import { Container, Typography, Box, Tabs, Tab, Paper } from '@mui/material';
import GitHubStats from '../components/GitHub/GitHubStats';
import CICDStatus from '../components/GitHub/CICDStatus';

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
      id={`github-tabpanel-${index}`}
      aria-labelledby={`github-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

const GitHubPage: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Box mb={4}>
        <Typography variant="h4" component="h1" gutterBottom>
          GitHub Integration
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Monitor repository activity, track issues and pull requests, and view CI/CD status.
        </Typography>
      </Box>
      
      <Paper sx={{ mb: 2 }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          indicatorColor="primary"
          textColor="primary"
          variant="fullWidth"
        >
          <Tab label="Repository Stats" />
          <Tab label="CI/CD Pipeline" />
        </Tabs>
      </Paper>

      <TabPanel value={tabValue} index={0}>
        <GitHubStats />
      </TabPanel>
      <TabPanel value={tabValue} index={1}>
        <CICDStatus />
      </TabPanel>
    </Container>
  );
};

export default GitHubPage;