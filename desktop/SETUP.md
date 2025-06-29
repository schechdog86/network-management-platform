# Network Manager Qt Desktop Application Setup

## Overview
The Network Manager Qt Desktop Application provides a modern GUI interface for network management with features including:
- Real-time network monitoring
- Device management and control
- Backup management
- AI-powered assistant
- Dark/Light theme support
- WebSocket-based real-time updates

## Requirements
- Python 3.8 or higher
- Qt6 (via PySide6)
- Backend API server running (optional, app works offline)

## Installation

### 1. Install System Dependencies
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3-pip python3-venv libgl1-mesa-glx

# For Qt6 support
sudo apt install qt6-base-dev
```

### 2. Create Virtual Environment (Recommended)
```bash
cd /home/edward/network/desktop
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install Additional Dependencies if Needed
```bash
# If you encounter import errors
pip install websocket-client
```

## Running the Application

### Basic Launch
```bash
cd /home/edward/network
python3 desktop/main.py
```

### With Virtual Environment
```bash
cd /home/edward/network/desktop
source venv/bin/activate
cd ..
python desktop/main.py
```

## Features

### 1. Theme Support
- **Light Theme**: Default clean interface
- **Dark Theme**: Easy on the eyes for extended use
- **System Theme**: Follows OS theme (future feature)

Access via: View → Theme → [Light/Dark/System]

### 2. Backend Integration
- The app automatically connects to the backend API at `http://localhost:8000`
- Works in offline mode if backend is unavailable
- Real-time updates via WebSocket when connected

### 3. Network Overview
- Real-time device discovery and status
- Network scanning capabilities
- Device inventory management

### 4. Monitoring Dashboard
- CPU and memory usage graphs
- Network traffic visualization
- Alert notifications

### 5. AI Assistant
- Natural language command processing
- Intelligent automation suggestions
- Context-aware responses

### 6. Backup Management
- Schedule and manage backups
- View backup history
- Restore operations

## Configuration

The application stores its configuration at:
```
~/.config/network-manager/desktop-config.json
```

Default configuration includes:
```json
{
  "api": {
    "base_url": "http://localhost:8000",
    "timeout": 30
  },
  "ui": {
    "theme": "light",
    "refresh_interval": 5
  }
}
```

## Troubleshooting

### PySide6 Import Errors
```bash
# Ensure PySide6 is properly installed
pip install --force-reinstall PySide6
```

### Backend Connection Issues
- Ensure the backend server is running
- Check firewall settings
- Verify API URL in configuration

### Theme Not Applying
- Restart the application after theme change
- Check Qt platform plugin is available

### Performance Issues
- Adjust refresh interval in settings
- Disable real-time updates if on slow connection

## Development

### Project Structure
```
desktop/
├── main.py              # Entry point
├── requirements.txt     # Python dependencies
├── ui/
│   └── main_window.py   # Main application window
├── components/
│   ├── network_overview.py
│   ├── monitoring.py
│   ├── ai_assistant.py
│   └── ...
└── utils/
    ├── api_client.py    # Backend API integration
    ├── theme_manager.py # Theme management
    └── config.py        # Configuration handling
```

### Adding New Features
1. Create new component in `components/`
2. Add to main window tabs
3. Integrate with API client for data
4. Add WebSocket handlers for real-time updates

## Testing

Run the test suite:
```bash
python3 desktop/test_qt_app.py
```

## Known Issues
- WebSocket reconnection may need manual refresh
- Some graphs may flicker on theme change
- AI assistant requires backend for full functionality

## Future Enhancements
- System tray integration
- Notification center
- Plugin system
- Custom dashboard layouts
- Export/import configurations