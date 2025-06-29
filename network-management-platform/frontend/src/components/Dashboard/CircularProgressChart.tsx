import React from 'react';
import { Box, Paper, Typography, CircularProgress, useTheme } from '@mui/material';

interface CircularProgressChartProps {
  title: string;
  value: number;
  unit?: string;
  color?: string;
  size?: number;
  thickness?: number;
  maxValue?: number;
}

const CircularProgressChart: React.FC<CircularProgressChartProps> = ({
  title,
  value,
  unit = '',
  color,
  size = 100,
  thickness = 4,
  maxValue = 100,
}) => {
  const theme = useTheme();
  
  // Normalize value to percentage if maxValue is provided
  const percentage = Math.min((value / maxValue) * 100, 100);
  
  // Choose color based on value if not provided
  const getColor = () => {
    if (color) return color;
    
    if (percentage >= 90) return theme.palette.error.main;
    if (percentage >= 70) return theme.palette.warning.main;
    if (percentage >= 50) return theme.palette.info.main;
    return theme.palette.success.main;
  };

  const progressColor = getColor();

  return (
    <Paper 
      elevation={1} 
      sx={{ 
        p: 2, 
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        minHeight: size + 80,
        justifyContent: 'center'
      }}
    >
      <Typography 
        variant="subtitle2" 
        component="h3" 
        gutterBottom
        sx={{ 
          color: theme.palette.text.primary,
          fontWeight: 500,
          textAlign: 'center',
          mb: 2
        }}
      >
        {title}
      </Typography>
      
      <Box sx={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {/* Background circle */}
        <CircularProgress
          variant="determinate"
          value={100}
          size={size}
          thickness={thickness}
          sx={{
            color: theme.palette.action.disabled,
            position: 'absolute',
          }}
        />
        
        {/* Progress circle */}
        <CircularProgress
          variant="determinate"
          value={percentage}
          size={size}
          thickness={thickness}
          sx={{
            color: progressColor,
            '& .MuiCircularProgress-circle': {
              strokeLinecap: 'round',
            },
          }}
        />
        
        {/* Value text */}
        <Box
          sx={{
            position: 'absolute',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Typography
            variant="h6"
            component="div"
            sx={{ 
              color: theme.palette.text.primary,
              fontWeight: 600,
              fontSize: size > 80 ? '1.25rem' : '1rem'
            }}
          >
            {value.toFixed(1)}
          </Typography>
          {unit && (
            <Typography
              variant="caption"
              sx={{ 
                color: theme.palette.text.secondary,
                fontSize: size > 80 ? '0.75rem' : '0.625rem',
                lineHeight: 1
              }}
            >
              {unit}
            </Typography>
          )}
        </Box>
      </Box>
      
      {/* Status indicator */}
      <Box sx={{ mt: 1 }}>
        <Typography
          variant="caption"
          sx={{
            color: progressColor,
            fontWeight: 500,
            fontSize: '0.7rem'
          }}
        >
          {percentage >= 90 ? 'Critical' : 
           percentage >= 70 ? 'High' : 
           percentage >= 50 ? 'Medium' : 'Normal'}
        </Typography>
      </Box>
    </Paper>
  );
};

export default CircularProgressChart;