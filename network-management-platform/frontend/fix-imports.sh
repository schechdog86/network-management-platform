#!/bin/bash

# Script to fix unused imports in TypeScript files

echo "Fixing unused imports in TypeScript files..."

# Fix ChatInterface.tsx
sed -i '32s/const { send,/const {/' src/components/Chat/ChatInterface.tsx

# Fix ErrorBoundary.tsx - remove unused React import
sed -i '1s/import React,/import/' src/components/Common/ErrorBoundary.tsx

# Fix Layout.tsx
sed -i '/Typography,/d' src/components/Layout/Layout.tsx
sed -i '/IconButton,/d' src/components/Layout/Layout.tsx
sed -i '/import.*mui\/icons-material/d' src/components/Layout/Layout.tsx

# Fix Sidebar.tsx
sed -i '/Drawer,/d' src/components/Layout/Sidebar.tsx
sed -i '/BackupIcon/d' src/components/Layout/Sidebar.tsx
sed -i '/ConsoleIcon/d' src/components/Layout/Sidebar.tsx

# Fix TopBar.tsx
sed -i '/AccountCircle,/d' src/components/Layout/TopBar.tsx

# Fix PredictiveMaintenancePage
sed -i '66s/event: React.SyntheticEvent/_: React.SyntheticEvent/' src/pages/PredictiveMaintenancePage.tsx

# Fix other files
sed -i '/StopIcon/d' src/pages/MetricsPage.tsx
sed -i '/PowerIcon/d' src/pages/DevicesPage.tsx
sed -i '/, Device/s/, Device//' src/pages/DevicesPage.tsx
sed -i '/LoadingSpinner/d' src/pages/NetworkPage.tsx
sed -i '/Divider,/d' src/pages/SettingsPage.tsx

echo "Import fixes completed!"