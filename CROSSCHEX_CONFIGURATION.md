# CrossChex Cloud API Configuration Guide

## Overview

The Hamptons app supports **two distinct configuration approaches** for CrossChex API integration, providing flexibility for different deployment scenarios:

1. **Multi-Device Configuration** (Recommended) - Supports multiple CrossChex Cloud API endpoints
2. **Legacy Single Configuration** (Deprecated) - Single global API configuration

Both methods function correctly with automatic fallback logic, allowing seamless migration from legacy to multi-device setups.

---

## Configuration Modes

### 1. Multi-Device Configuration (Recommended)

**Use When:**
- Managing attendance from multiple CrossChex Cloud regions (US, EU, etc.)
- Different API credentials per device/location
- Scalable multi-location deployments
- Need individual device monitoring and control

**Location:** CrossChex Settings → Basic Settings → API Configurations (child table)

**Required Fields per Row:**
- **Configuration Name**: Descriptive name (e.g., "EU1", "US-HQ", "Dubai Office")
- **API URL**: Region-specific endpoint
  - US: `https://api.us.crosschexcloud.com/`
  - EU: `https://api.eu.crosschexcloud.com/`
- **API Key**: Device-specific API key from CrossChex Cloud
- **API Secret**: Device-specific API secret (password field)

**Features:**
- ✅ Individual token management per device
- ✅ Per-device connection testing
- ✅ Independent sync status tracking
- ✅ Parallel sync from all configured devices
- ✅ Consolidated sync reporting

**Example Configuration:**
```
Row 1: EU1  | https://api.eu.crosschexcloud.com/ | [api_key] | [secret]
Row 2: US1  | https://api.us.crosschexcloud.com/ | [api_key] | [secret]
Row 3: US2  | https://api.us.crosschexcloud.com/ | [api_key] | [secret]
```

---

### 2. Legacy Single Configuration (Deprecated)

**Use When:**
- Single CrossChex Cloud device/region
- Simple deployments with one API endpoint
- Migrating existing installations

**Location:** CrossChex Settings → Basic Settings → Legacy Single Configuration (collapsible section)

**Required Fields:**
- **API URL**: Single endpoint URL
- **API Key**: Global API key
- **API Secret**: Global API secret

**Limitations:**
- ⚠️ Single device support only
- ⚠️ No per-device status tracking
- ⚠️ Deprecated - will be removed in future versions

---

## Priority & Fallback Logic

The system implements **smart configuration detection** with the following priority:

### Validation Logic (on Save)
```python
1. IF enable_realtime_sync is checked:
   2. Check for multi-device configurations
   3. IF api_configurations table has rows:
      → Validate each row (URL, Key, Secret required)
   4. ELSE check legacy fields:
      → Validate legacy API URL, Key, Secret
   5. IF neither configured:
      → Throw error: "Configure either mode"
```

### Sync Logic (Scheduled Jobs)
```python
1. Check enable_realtime_sync flag
2. IF disabled → Exit silently
3. IF api_configurations exists and has rows:
   → Loop through each device
   → Sync from all devices
   → Aggregate results
4. ELSE:
   → Use legacy global settings
   → Sync from single endpoint
```

### Token Refresh Logic (Hourly)
```python
1. Check enable_realtime_sync flag
2. IF disabled → Exit
3. IF api_configurations has rows:
   → Check each device token expiry
   → Refresh tokens expiring within 30 minutes
4. ELSE:
   → Check legacy token expiry
   → Refresh if needed
```

---

## Setup Instructions

### Multi-Device Setup (Recommended)

1. **Navigate to CrossChex Settings**
   - Desk → Search "CrossChex Settings"

2. **Add API Configurations**
   - Expand "API Configurations" section
   - Click "Add Row"
   - Fill in Configuration Name, API URL, API Key, API Secret
   - Repeat for each device/region

3. **Test Each Connection**
   - Click "Test Connection" button in each row
   - Verify "Connected" status
   - Check token generation

4. **Enable Realtime Sync**
   - Check "Enable Realtime Sync" checkbox
   - Set "Sync Frequency" (default: 15 minutes)
   - Save document

5. **Verify Auto-Sync**
   - Navigate to "Status & Controls" tab
   - Check "Last Sync Time" and "Last Sync Status"
   - Wait 15 minutes for first auto-sync
   - Or click "Sync Now" for immediate sync

### Legacy Single Configuration Setup

1. **Navigate to CrossChex Settings**
   - Desk → Search "CrossChex Settings"

2. **Configure Legacy Fields**
   - Expand "Legacy Single Configuration (Deprecated)"
   - Enter API URL (e.g., `https://api.us.crosschexcloud.com/`)
   - Enter API Key
   - Enter API Secret

3. **Test Connection**
   - Click "Test Connection" button at top
   - Verify connection successful

4. **Enable Sync**
   - Check "Enable Realtime Sync"
   - Save document

---

## Migration Path: Legacy → Multi-Device

**Zero-Downtime Migration:**

1. **Document Current Settings**
   - Note existing API URL, Key, Secret
   - Check Last Sync Status

2. **Add First Multi-Device Config**
   - Keep legacy fields populated
   - Add one row in API Configurations table
   - Copy legacy credentials to row 1
   - Save document

3. **Test Multi-Device Config**
   - Click "Test Connection" on row 1
   - Verify token generation
   - Click "Sync Now" to test sync

4. **Add Additional Devices**
   - Add more rows as needed
   - Test each configuration

5. **Clear Legacy Fields (Optional)**
   - Once multi-device working, legacy fields ignored
   - Can clear for clarity
   - System automatically uses multi-device mode

---

## Scheduled Jobs

### Auto-Sync Scheduler
- **Frequency**: Every 15 minutes (configurable via cron: `*/15 * * * *`)
- **Function**: `scheduled_attendance_sync()`
- **Location**: [`hooks.py`](file:///Users/sammishthundiyil/frappe-bench-oman/apps/hamptons/hamptons/hooks.py) L151
- **Behavior**:
  - Checks `enable_realtime_sync` flag
  - Exits if disabled
  - Uses multi-device if configured, else falls back to legacy
  - Updates `last_sync_time` and `last_sync_status`

### Token Refresh Scheduler
- **Frequency**: Hourly
- **Function**: `check_and_refresh_token()`
- **Location**: [`hooks.py`](file:///Users/sammishthundiyil/frappe-bench-oman/apps/hamptons/hamptons/hooks.py) L154
- **Behavior**:
  - Checks all device tokens (or legacy token)
  - Refreshes tokens expiring within 30 minutes
  - Prevents authentication failures

---

## Troubleshooting

### Validation Error: "API Key is required when sync is enabled"

**Cause**: `enable_realtime_sync` is checked but neither configuration mode has complete credentials.

**Solution**:
- **For Multi-Device**: Ensure all rows in API Configurations table have URL, Key, and Secret
- **For Legacy**: Ensure global API URL, API Key, and API Secret are filled
- **Quick Fix**: Add at least one complete configuration in either mode

### Scheduler Not Running

**Symptoms**: `last_sync_time` not updating, no new attendance records

**Diagnosis Steps**:
1. Check `enable_realtime_sync` checkbox is enabled
2. Run: `bench --site hamptons.local scheduler status`
3. Verify scheduler is enabled
4. Manually test: `bench --site hamptons.local execute hamptons.hamptons.doctype.crosschex_settings.crosschex_settings.scheduled_attendance_sync`

**Common Causes**:
- ❌ `enable_realtime_sync` disabled → Scheduler exits silently
- ❌ Scheduler service stopped → Restart with `bench --site hamptons.local scheduler enable`
- ❌ No valid configurations → Check validation

### Multi-Device Not Syncing

**Check**:
1. Verify each row has "Connected" status
2. Check `last_sync_status` for device-specific errors
3. Review Error Log for API failures
4. Ensure tokens are valid (check `token_expires` datetime)

**Manual Sync Per Device**:
- Click "Sync Now" button in specific device row
- Check device's `last_sync_status` field

### Token Expiration Issues

**Symptoms**: Sync fails with authentication errors after 24 hours

**Solution**:
- Tokens auto-refresh hourly (30-minute buffer)
- Manually refresh: Click "Reset Token" → "Test Connection"
- Check Error Log for token refresh failures

---

## Configuration File Reference

### Validation Logic
**File**: [`crosschex_settings.py`](file:///Users/sammishthundiyil/frappe-bench-oman/apps/hamptons/hamptons/hamptons/doctype/crosschex_settings/crosschex_settings.py)
**Lines**: 15-47
**Logic**: Validates multi-device rows OR legacy fields when sync enabled

### Scheduled Sync
**File**: [`crosschex_settings.py`](file:///Users/sammishthundiyil/frappe-bench-oman/apps/hamptons/hamptons/hamptons/doctype/crosschex_settings/crosschex_settings.py)
**Lines**: 349-408
**Function**: `scheduled_attendance_sync()`
**Logic**: Loops through devices OR uses legacy, aggregates results

### Token Refresh
**File**: [`crosschex_settings.py`](file:///Users/sammishthundiyil/frappe-bench-oman/apps/hamptons/hamptons/hamptons/doctype/crosschex_settings/crosschex_settings.py)
**Lines**: 410-456
**Function**: `check_and_refresh_token()`
**Logic**: Refreshes device tokens OR legacy token

### Individual Device Sync
**File**: [`crosschex_settings.py`](file:///Users/sammishthundiyil/frappe-bench-oman/apps/hamptons/hamptons/hamptons/doctype/crosschex_settings/crosschex_settings.py)
**Lines**: 524-720
**Function**: `sync_individual_device(api_url, api_key, config_row_name, config_name)`
**Logic**: Generates token, fetches records, processes attendance

---

## Testing Procedures

### Test Multi-Device Configuration

```bash
# 1. Verify scheduler is running
bench --site hamptons.local scheduler status

# 2. Test sync function directly
bench --site hamptons.local execute hamptons.hamptons.doctype.crosschex_settings.crosschex_settings.scheduled_attendance_sync

# 3. Check sync status
bench --site hamptons.local execute hamptons.hamptons.doctype.crosschex_settings.crosschex_settings.get_crosschex_status

# 4. View logs
tail -f sites/hamptons.local/logs/worker.error.log
```

### Test Legacy Configuration

```bash
# 1. Manual sync via legacy method
bench --site hamptons.local execute hamptons.crosschex_cloud.api.sync.manual_sync_crosschex_cloud

# 2. Verify token generation
bench --site hamptons.local execute "print(frappe.get_single('Crosschex Settings').get_password('token'))"

# 3. Check connection status
bench --site hamptons.local execute "print(frappe.get_single('Crosschex Settings').connection_status)"
```

### Validate Configuration Switching

```python
# In Frappe Console (bench --site hamptons.local console)
settings = frappe.get_single('Crosschex Settings')

# Check active mode
has_multi = settings.api_configurations and len(settings.api_configurations) > 0
has_legacy = bool(settings.api_key and settings.api_secret)

print(f"Multi-Device Mode: {has_multi}")
print(f"Legacy Mode: {has_legacy}")
print(f"Active Mode: {'Multi-Device' if has_multi else 'Legacy'}")
```

---

## Best Practices

### 1. Use Multi-Device for New Deployments
- More flexible and scalable
- Better monitoring per device
- Easier to add/remove devices

### 2. Keep Legacy Populated During Migration
- Provides fallback during transition
- No service interruption
- Easy rollback if needed

### 3. Monitor Sync Status Regularly
- Check "Last Sync Status" field daily
- Set up email alerts for sync failures
- Review Error Log weekly

### 4. Test Connections After Credential Changes
- Always click "Test Connection" after updating credentials
- Verify token generation successful
- Perform manual sync to confirm

### 5. Token Management
- Tokens auto-expire after 24 hours
- Hourly refresh prevents expiration
- Manual reset available via "Reset Token" button

---

## API Endpoints

### CrossChex Cloud Regions

| Region | API URL | Use For |
|--------|---------|---------|
| US | `https://api.us.crosschexcloud.com/` | North America, Asia-Pacific |
| EU | `https://api.eu.crosschexcloud.com/` | Europe, Middle East, Africa |

### Token Generation Endpoint
```http
POST https://api.{region}.crosschexcloud.com/
Content-Type: application/json

{
  "header": {
    "nameSpace": "authorize.token",
    "nameAction": "token",
    "version": "1.0",
    "requestId": "{uuid}",
    "timestamp": "{iso8601_timestamp}"
  },
  "payload": {
    "api_key": "{your_api_key}",
    "api_secret": "{your_api_secret}"
  }
}
```

### Attendance Fetch Endpoint
```http
POST https://api.{region}.crosschexcloud.com/
Content-Type: application/json

{
  "header": {
    "nameSpace": "attendance.record",
    "nameAction": "getrecord",
    "version": "1.0",
    "requestId": "{uuid}",
    "timestamp": "{iso8601_timestamp}"
  },
  "authorize": {
    "type": "token",
    "token": "{access_token}"
  },
  "payload": {
    "begin_time": "{start_datetime}",
    "end_time": "{end_datetime}",
    "order": "asc",
    "page": 1,
    "per_page": 1000
  }
}
```

---

## Support & Maintenance

### Logs Location
- **Worker Logs**: `sites/hamptons.local/logs/worker.error.log`
- **Scheduler Logs**: `sites/hamptons.local/logs/scheduler.log`
- **Error Log DocType**: Search "Error Log" in Desk

### Key Configuration Fields

| Field | Location | Purpose |
|-------|----------|---------|
| `enable_realtime_sync` | Basic Settings | Master on/off switch |
| `api_configurations` | Basic Settings | Multi-device config table |
| `api_url` (legacy) | Legacy Section | Single endpoint URL |
| `sync_frequency` | Basic Settings | Minutes between syncs |
| `last_sync_time` | Status Tab | Last successful sync |
| `last_sync_status` | Status Tab | Detailed sync results |
| `connection_status` | Status Tab | Connection health |

### Version History
- **v1.0**: Legacy single configuration only
- **v2.0**: Added multi-device support with fallback logic
- **v2.1**: Enhanced validation, dual-mode support, auto-fallback

---

## Summary

The CrossChex Settings dual configuration system provides maximum flexibility:

✅ **Multi-Device Mode**: Scalable, per-device monitoring, recommended for new deployments  
✅ **Legacy Mode**: Simple, single-endpoint, maintained for backward compatibility  
✅ **Automatic Fallback**: Checks multi-device first, uses legacy if empty  
✅ **Zero Downtime Migration**: Add multi-device configs while legacy still works  
✅ **Robust Validation**: Ensures at least one complete configuration exists  
✅ **Smart Scheduling**: Scheduler adapts to active configuration mode  

For questions or issues, refer to the Error Log DocType or review worker logs.
