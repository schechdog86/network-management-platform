import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  CircularProgress,
  Alert,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Tooltip,
  LinearProgress,
  Paper,
  Divider,
} from '@mui/material';
import {
  GitHub as GitHubIcon,
  Star as StarIcon,
  ForkRight as ForkIcon,
  BugReport as BugIcon,
  Extension as ExtensionIcon,
  PullRequest as PullRequestIcon,
  Commit as CommitIcon,
  Schedule as ScheduleIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import api from '../../services/api';
import '../../styles/github.css';

interface RepositoryStats {
  repository: {
    name: string;
    description: string;
    url: string;
    stars: number;
    forks: number;
    disk_usage_mb: number;
    is_private: boolean;
    default_branch: string;
    languages: Record<string, number>;
  };
  activity: {
    commits_last_7_days: number;
    commits_last_30_days: number;
    total_open_issues: number;
    bug_issues: number;
    enhancement_issues: number;
    open_pull_requests: number;
  };
  recent_activity: {
    latest_commit: any;
    latest_issue: any;
    latest_pr: any;
  };
}

interface GitHubCommit {
  oid: string;
  message: string;
  committed_date: string;
  author_name: string;
  author_email: string;
  additions: number;
  deletions: number;
}

interface WorkflowRun {
  id: string;
  name: string;
  status: string;
  conclusion: string | null;
  created_at: string;
  updated_at: string;
  head_sha: string;
  head_branch: string;
  run_number: number;
  event: string;
}

const GitHubStats: React.FC = () => {
  const [stats, setStats] = useState<RepositoryStats | null>(null);
  const [commits, setCommits] = useState<GitHubCommit[]>([]);
  const [workflowRuns, setWorkflowRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchGitHubData = async () => {
    try {
      setError(null);
      const [statsResponse, commitsResponse, workflowsResponse] = await Promise.all([
        api.get('/api/v1/github/stats/summary'),
        api.get('/api/v1/github/commits?limit=5'),
        api.get('/api/v1/github/workflow-runs?limit=5'),
      ]);

      setStats(statsResponse.data);
      setCommits(commitsResponse.data);
      setWorkflowRuns(workflowsResponse.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch GitHub data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchGitHubData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchGitHubData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchGitHubData();
  };

  const getLanguageColor = (language: string): string => {
    const colors: Record<string, string> = {
      TypeScript: '#2b7489',
      JavaScript: '#f1e05a',
      Python: '#3572A5',
      HTML: '#e34c26',
      CSS: '#563d7c',
      Shell: '#89e051',
      Dockerfile: '#384d54',
    };
    return colors[language] || '#959da5';
  };

  const getWorkflowStatusIcon = (status: string, conclusion: string | null) => {
    if (status === 'COMPLETED') {
      if (conclusion === 'SUCCESS') {
        return <CheckCircleIcon color="success" />;
      } else if (conclusion === 'FAILURE') {
        return <ErrorIcon color="error" />;
      }
    }
    return <CircularProgress size={20} />;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={400}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!stats) {
    return (
      <Alert severity="info" sx={{ m: 2 }}>
        No GitHub data available
      </Alert>
    );
  }

  const totalLanguageSize = Object.values(stats.repository.languages).reduce((a, b) => a + b, 0);

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5" gutterBottom>
          GitHub Repository Stats
        </Typography>
        <Tooltip title="Refresh data">
          <IconButton onClick={handleRefresh} disabled={refreshing}>
            <RefreshIcon className={refreshing ? 'rotating' : ''} />
          </IconButton>
        </Tooltip>
      </Box>

      <Grid container spacing={3}>
        {/* Repository Overview */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <GitHubIcon sx={{ mr: 1 }} />
                <Typography variant="h6">{stats.repository.name}</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" mb={2}>
                {stats.repository.description}
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Box display="flex" alignItems="center">
                    <StarIcon sx={{ color: '#f0ad4e', mr: 1 }} />
                    <Typography variant="h4">{stats.repository.stars}</Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary">Stars</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Box display="flex" alignItems="center">
                    <ForkIcon sx={{ mr: 1 }} />
                    <Typography variant="h4">{stats.repository.forks}</Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary">Forks</Typography>
                </Grid>
              </Grid>

              <Box mt={2}>
                <Typography variant="body2" color="text.secondary">
                  Disk Usage: {stats.repository.disk_usage_mb.toFixed(2)} MB
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Default Branch: {stats.repository.default_branch}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Activity Stats */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Activity Overview
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Box>
                    <Typography variant="h4">{stats.activity.commits_last_7_days}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Commits (7 days)
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box>
                    <Typography variant="h4">{stats.activity.commits_last_30_days}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Commits (30 days)
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={4}>
                  <Box display="flex" alignItems="center">
                    <BugIcon sx={{ mr: 1, color: '#d73a49' }} />
                    <Typography variant="h5">{stats.activity.bug_issues}</Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary">Bugs</Typography>
                </Grid>
                <Grid item xs={4}>
                  <Box display="flex" alignItems="center">
                    <ExtensionIcon sx={{ mr: 1, color: '#0366d6' }} />
                    <Typography variant="h5">{stats.activity.enhancement_issues}</Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary">Enhancements</Typography>
                </Grid>
                <Grid item xs={4}>
                  <Box display="flex" alignItems="center">
                    <PullRequestIcon sx={{ mr: 1, color: '#6f42c1' }} />
                    <Typography variant="h5">{stats.activity.open_pull_requests}</Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary">Open PRs</Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Languages */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Languages
              </Typography>
              {Object.entries(stats.repository.languages)
                .sort(([, a], [, b]) => b - a)
                .map(([language, size]) => {
                  const percentage = (size / totalLanguageSize) * 100;
                  return (
                    <Box key={language} mb={1}>
                      <Box display="flex" justifyContent="space-between" alignItems="center">
                        <Typography variant="body2">{language}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {percentage.toFixed(1)}%
                        </Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={percentage}
                        sx={{
                          height: 8,
                          borderRadius: 4,
                          backgroundColor: '#e0e0e0',
                          '& .MuiLinearProgress-bar': {
                            backgroundColor: getLanguageColor(language),
                          },
                        }}
                      />
                    </Box>
                  );
                })}
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Commits */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Commits
              </Typography>
              <List dense>
                {commits.map((commit) => (
                  <ListItem key={commit.oid}>
                    <ListItemIcon>
                      <CommitIcon />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Typography variant="body2" noWrap>
                          {commit.message.split('\n')[0]}
                        </Typography>
                      }
                      secondary={
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            {commit.author_name} • {format(new Date(commit.committed_date), 'MMM d, yyyy')}
                          </Typography>
                          <Box display="flex" gap={1} mt={0.5}>
                            <Chip
                              label={`+${commit.additions}`}
                              size="small"
                              sx={{ backgroundColor: '#d1f5d3', height: 20 }}
                            />
                            <Chip
                              label={`-${commit.deletions}`}
                              size="small"
                              sx={{ backgroundColor: '#ffdce0', height: 20 }}
                            />
                          </Box>
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        {/* CI/CD Status */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                CI/CD Status
              </Typography>
              <List>
                {workflowRuns.map((run) => (
                  <ListItem key={run.id}>
                    <ListItemIcon>
                      {getWorkflowStatusIcon(run.status, run.conclusion)}
                    </ListItemIcon>
                    <ListItemText
                      primary={run.name}
                      secondary={
                        <Box display="flex" gap={2}>
                          <Typography variant="caption" color="text.secondary">
                            Run #{run.run_number} • {run.event}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {format(new Date(run.created_at), 'MMM d, yyyy HH:mm')}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Branch: {run.head_branch}
                          </Typography>
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default GitHubStats;