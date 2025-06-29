import React, { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';
import { Box, Paper, Typography, useTheme } from '@mui/material';
import { format } from 'date-fns';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
  Filler
);

interface MetricsDataPoint {
  timestamp: string;
  value: number;
}

interface MetricsChartProps {
  title: string;
  data: MetricsDataPoint[];
  unit?: string;
  color?: string;
  height?: number;
  showFill?: boolean;
  maxValue?: number;
  minValue?: number;
}

const MetricsChart: React.FC<MetricsChartProps> = ({
  title,
  data,
  unit = '',
  color,
  height = 300,
  showFill = true,
  maxValue,
  minValue,
}) => {
  const theme = useTheme();
  
  // Use theme colors if no color specified
  const chartColor = color || theme.palette.primary.main;
  
  const chartData = useMemo(() => {
    const sortedData = [...data].sort((a, b) => 
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    return {
      labels: sortedData.map(d => new Date(d.timestamp)),
      datasets: [
        {
          label: title,
          data: sortedData.map(d => d.value),
          borderColor: chartColor,
          backgroundColor: showFill ? `${chartColor}20` : 'transparent',
          borderWidth: 2,
          fill: showFill,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: chartColor,
          pointHoverBorderColor: '#fff',
          pointHoverBorderWidth: 2,
        },
      ],
    };
  }, [data, title, chartColor, showFill]);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      intersect: false,
      mode: 'index' as const,
    },
    plugins: {
      legend: {
        display: false, // We show the title separately
      },
      tooltip: {
        backgroundColor: theme.palette.background.paper,
        titleColor: theme.palette.text.primary,
        bodyColor: theme.palette.text.primary,
        borderColor: theme.palette.divider,
        borderWidth: 1,
        cornerRadius: 8,
        displayColors: false,
        callbacks: {
          title: (context: any) => {
            return format(new Date(context[0].parsed.x), 'MMM dd, HH:mm:ss');
          },
          label: (context: any) => {
            return `${context.parsed.y.toFixed(2)}${unit}`;
          },
        },
      },
    },
    scales: {
      x: {
        type: 'time' as const,
        time: {
          displayFormats: {
            minute: 'HH:mm',
            hour: 'HH:mm',
            day: 'MMM dd',
          },
        },
        grid: {
          color: theme.palette.divider,
          drawBorder: false,
        },
        ticks: {
          color: theme.palette.text.secondary,
          maxTicksLimit: 8,
        },
      },
      y: {
        beginAtZero: minValue === undefined,
        min: minValue,
        max: maxValue,
        grid: {
          color: theme.palette.divider,
          drawBorder: false,
        },
        ticks: {
          color: theme.palette.text.secondary,
          callback: function(value: any) {
            return `${value}${unit}`;
          },
        },
      },
    },
    elements: {
      point: {
        hitRadius: 10,
      },
    },
    animation: {
      duration: 300,
    },
  }), [theme, unit, maxValue, minValue]);

  return (
    <Paper 
      elevation={1} 
      sx={{ 
        p: 2, 
        height: height + 60,
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      <Typography 
        variant="h6" 
        component="h3" 
        gutterBottom
        sx={{ 
          color: theme.palette.text.primary,
          fontWeight: 500,
          mb: 2
        }}
      >
        {title}
      </Typography>
      
      <Box sx={{ flexGrow: 1, position: 'relative' }}>
        {data.length > 0 ? (
          <Line data={chartData} options={options} />
        ) : (
          <Box 
            display="flex" 
            alignItems="center" 
            justifyContent="center" 
            height="100%"
          >
            <Typography variant="body2" color="text.secondary">
              No data available
            </Typography>
          </Box>
        )}
      </Box>
    </Paper>
  );
};

export default MetricsChart;