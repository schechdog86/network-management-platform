# Network Management Desktop Application

A comprehensive Qt6/PySide6-based desktop application for network management, monitoring, and administration.

## Features

- **Network Overview**: Real-time dashboard showing all network devices and their status
- **Device Management**: Add, remove, and configure network devices
- **Monitoring**: Real-time performance metrics and alerts
- **Backup Management**: Automated backup scheduling and restoration
- **AI Assistant**: Natural language interface for network operations
- **Settings**: Comprehensive configuration options

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

```bash
python main.py
```

Or make the script executable:
```bash
chmod +x main.py
./main.py
```

## Project Structure

```
desktop/
├── main.py              # Application entry point
├── ui/                  # UI components
│   └── main_window.py   # Main application window
├── components/          # Feature-specific widgets
│   ├── network_overview.py
│   ├── device_manager.py
│   ├── monitoring.py
│   ├── backup_manager.py
│   ├── ai_assistant.py
│   └── settings.py
├── utils/               # Utility modules
│   └── config.py        # Configuration management
└── requirements.txt     # Python dependencies
```

## Configuration

The application stores its configuration in:
- Linux/Mac: `~/.config/network-manager/desktop-config.json`
- Windows: `%APPDATA%/network-manager/desktop-config.json`

## Development

To run tests:
```bash
pytest
```

To format code:
```bash
black .
```

To lint code:
```bash
pylint desktop/
```

## Future Enhancements

- Integration with backend API
- Real-time WebSocket updates
- Advanced AI capabilities with LangChain
- Custom themes and plugins
- Multi-language support