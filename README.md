## Hamptons

ERPNext custom app for Hamptons with CrossChex Cloud attendance integration.

## Features

### CrossChex Cloud Integration

This app provides seamless integration with CrossChex Cloud biometric attendance system:

- **Multi-Device Configuration**: Support for multiple CrossChex Cloud devices with different API endpoints (EU and US regions)
- **Real-time Attendance Sync**: Automatic synchronization of attendance records from CrossChex Cloud devices
- **Individual Device Management**: Test connections and sync attendance data for each device independently
- **Employee Mapping**: Maps CrossChex employee IDs to ERPNext employees using custom `attendance_device_id` field
- **Shift Integration**: Automatic shift assignment lookup for attendance records
- **Token Management**: Smart token generation and caching with expiry tracking

### Department Override

Custom department naming convention that removes company abbreviation suffix from department names.

## Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app hamptons
```

## Configuration

### CrossChex Cloud Setup

1. Navigate to **CrossChex Settings** in your ERPNext instance
2. Add API configurations for each CrossChex device in the **API Configurations** table:
   - **Configuration Name**: Friendly name for the device (e.g., "EU Office Main Entrance")
   - **API URL**: CrossChex Cloud API endpoint
     - EU Region: `https://api.eu.crosschexcloud.com/`
     - US Region: `https://api.us.crosschexcloud.com/`
   - **API Key**: Your CrossChex Cloud API key
   - **API Secret**: Your CrossChex Cloud API secret
3. Click **Test Connection** for each configuration to verify credentials
4. Enable **Real-time Sync** to start automatic synchronization

### Employee Setup

Ensure each employee in ERPNext has the `attendance_device_id` field populated with their CrossChex employee ID (workno). This field is required for the system to map attendance records correctly.

## Usage

### Manual Sync

Click the **Sync Now** button on any device configuration row to fetch the last 24 hours of attendance records from that specific device.

### Viewing Sync Status

Each device configuration displays:
- **Connection Status**: Current connection state (Connected/Error/Not Tested)
- **Last Sync Time**: Timestamp of the last successful sync
- **Last Sync Status**: Detailed status message with record count or error information
- **Token Status**: Token expiry and generation time

### Attendance Records

Synced attendance records are automatically created in ERPNext with:
- Employee mapping via `attendance_device_id`
- Shift assignment lookup
- Device information
- Check-in/Check-out log type

## Architecture

### File Structure

```
hamptons/
├── hamptons/
│   ├── doctype/
│   │   ├── crosschex_settings/           # Main settings doctype
│   │   └── crosschex_api_configuration/  # Child doctype for device configs
│   └── crosschex_cloud/
│       └── api/
│           ├── attendance.py             # Attendance processing logic
│           └── sync.py                   # Sync orchestration
└── overrides/
    └── department.py                     # Department naming override
```

### Key Components

- **CrossChex Settings**: Single doctype for global CrossChex configuration
- **CrossChex API Configuration**: Child table for managing multiple devices
- **Token Management**: Automatic token generation with 24-hour cache
- **Error Handling**: Comprehensive logging and status tracking
- **DateTime Handling**: MySQL-compatible datetime conversion from ISO 8601

## API Integration

The app uses CrossChex Cloud's REST API with the following endpoints:

- **Token Generation**: `POST /` with namespace `authorize.token`
- **Attendance Fetch**: `GET /` with namespace `attendance.list`

Tokens are cached and automatically renewed before expiry to minimize API calls.

## Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/hamptons
pre-commit install
```

Pre-commit is configured to use the following tools:

- ruff
- eslint
- prettier
- pyupgrade

## CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request

## License

MIT
