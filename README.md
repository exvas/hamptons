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

# Attendance Regularization Override System

## Overview

This system implements automatic attendance regularization generation based on employee check-ins and shift assignments. It validates shift assignments, monitors employee check-ins/check-outs, and automatically creates or updates attendance regularization documents when employees are late or leave early.

**Important**: The system now uses a consolidated approach where one Attendance Regularization document per employee per day can contain multiple employee checkins through a child table structure.

## Features

### 1. Shift Assignment Validation

The system validates shift assignments for employees with the following rules:

- **Active Shift Assignment**: Employees must have an active Shift Assignment record linking them to a valid Shift Type
- **Multiple Assignments**: If multiple shift assignments exist, the system uses the one with the most recent start date
- **Shift Type Validation**: The associated Shift Type must contain valid Start Time and End Time values

### 2. Automatic Regularization Generation

The system automatically generates Attendance Regularization documents when:

- **Late Entry**: Employee checks in after the Late Entry Grace Period specified in their Shift Type
- **Early Exit**: Employee checks out before the Shift End Time

**Important**: Attendance Regularization documents are only created after the scheduled Shift End Time has passed for the respective day.

## Components

### Main Module: `employee_checkin.py`

Location: [`hamptons/overrides/employee_checkin.py`](employee_checkin.py:1)

#### Key Functions

##### [`get_active_shift_assignment(employee, date=None)`](employee_checkin.py:10)

Gets the active Shift Assignment for an employee on a specific date.

**Parameters:**
- `employee`: Employee ID
- `date`: Date to check (defaults to today)

**Returns:** Shift Assignment document or None

**Logic:**
- Queries for active shift assignments on the given date
- If multiple assignments exist, returns the one with the most recent start date
- Only considers submitted (docstatus = 1) assignments

##### [`validate_shift_type(shift_type_name)`](employee_checkin.py:44)

Validates that the Shift Type has valid Start Time and End Time values.

**Parameters:**
- `shift_type_name`: Name of the Shift Type

**Returns:** Shift Type document

**Raises:** ValidationError if shift type is invalid

##### [`calculate_late_time(checkin_time, shift_start_time, grace_period_minutes=0)`](employee_checkin.py:62)

Calculates how late an employee is based on checkin time and shift start time.

**Parameters:**
- `checkin_time`: datetime of checkin
- `shift_start_time`: time object for shift start
- `grace_period_minutes`: grace period in minutes

**Returns:** Time difference as time object, or None if not late

**Logic:**
- Creates datetime for shift start on the checkin date
- Adds grace period to shift start time
- Compares checkin time with adjusted shift start time
- Returns time difference if employee is late

##### [`calculate_early_exit_time(checkout_time, shift_end_time)`](employee_checkin.py:88)

Calculates how early an employee checked out compared to shift end time.

**Parameters:**
- `checkout_time`: datetime of checkout
- `shift_end_time`: time object for shift end

**Returns:** Time difference as time object, or None if not early

##### [`should_create_regularization(checkin_doc)`](employee_checkin.py:109)

Determines if an Attendance Regularization should be created based on checkin/checkout.

**Parameters:**
- `checkin_doc`: Employee Checkin document

**Returns:** tuple (should_create: bool, reason: str, late_time: time or None)

**Logic:**
1. Gets active shift assignment for the employee
2. Validates the shift type
3. Checks if shift end time has passed (critical requirement)
4. For IN logs: Checks if employee is late (beyond grace period)
5. For OUT logs: Checks if employee left early
6. Returns decision with reason and calculated time difference

##### [`create_or_update_attendance_regularization(checkin_doc, shift_assignment, shift_type, late_time)`](employee_checkin.py:155)

Creates or updates an Attendance Regularization document for the employee checkin. This function now works with the consolidated structure where one regularization document per employee per day can contain multiple checkins.

**Parameters:**
- `checkin_doc`: Employee Checkin document
- `shift_assignment`: Shift Assignment document
- `shift_type`: Shift Type document
- `late_time`: Time difference as time object

**Logic:**
1. **Duplicate Check**: Verifies the checkin is not already linked to a regularization
2. **Existing Regularization Search**: Looks for existing regularization for the employee and posting date
3. **Update Path**: If a draft regularization exists:
   - Adds the new checkin to the `attendance_regularization_item` child table
   - Updates the late time if the current checkin is later
   - Saves the updated document
4. **Create Path**: If no draft regularization exists:
   - Creates new regularization document with:
     - Employee details
     - Posting date (checkin date)
     - Shift details
     - Initial late time
   - Adds the checkin to the child table
   - Inserts the document
5. Updates the Employee Checkin with regularization reference
6. Shows confirmation message to user

**Child Table Fields** (Attendance Regularization Item):
- `time`: Datetime of the checkin
- `log_type`: IN or OUT
- `device_id`: Location/Device identifier
- `employee_checkin`: Link to Employee Checkin document

##### [`on_employee_checkin_submit(doc, method=None)`](employee_checkin.py:295)

Hook function that runs after Employee Checkin is submitted.

**Parameters:**
- `doc`: Employee Checkin document
- `method`: Method name (not used)

**Flow:**
1. Calls `should_create_regularization()` to check if regularization is needed
2. If not needed, logs the reason and returns
3. If needed, gets shift assignment and shift type
4. Calls `create_or_update_attendance_regularization()` to create or update the document
5. Commits the transaction
6. Logs errors if creation/update fails

## Hook Registration

The system is registered in [`hamptons/hooks.py`](../hooks.py:140) using document events:

```python
doc_events = {
    "Employee Checkin": {
        "on_submit": "hamptons.overrides.employee_checkin.on_employee_checkin_submit"
    }
}
```

This ensures that every time an Employee Checkin is submitted, the system checks if an attendance regularization should be created.

## Workflow

### Complete Process Flow

1. **Employee Checks In/Out**
   - Employee uses attendance device or manual entry
   - Employee Checkin document is created and submitted

2. **Hook Triggers**
   - `on_employee_checkin_submit()` hook is triggered automatically

3. **Shift Assignment Validation**
   - System retrieves active shift assignment for the employee
   - If multiple assignments exist, uses the most recent one
   - Validates that shift type has valid start and end times

4. **Time Check**
   - System checks if current time is past the shift end time
   - If not, regularization creation is skipped (will be created later)

5. **Late Entry Check (for IN logs)**
   - Calculates time difference between checkin and shift start time
   - Accounts for grace period specified in shift type
   - If late, marks for regularization

6. **Early Exit Check (for OUT logs)**
   - Calculates time difference between checkout and shift end time
   - If early, marks for regularization

7. **Regularization Creation/Update**
   - **Check for Existing Regularization**:
     - Searches for draft regularization for the employee and posting date
   - **If Draft Exists**:
     - Adds the checkin to the existing regularization's child table
     - Updates late time if this checkin is later
   - **If No Draft Exists**:
     - Creates new Attendance Regularization document with:
       - Employee details
       - Posting date (checkin date)
       - Shift details
       - Initial late time calculation
       - Status: "Open" (pending approval)
     - Adds checkin to the child table (Attendance Regularization Item)
   - Updates Employee Checkin with regularization reference

8. **Multiple Checkins Per Day**
   - System consolidates all late/early checkins for an employee on a single date
   - Each checkin is stored as a separate row in the child table
   - The regularization shows the maximum late time among all checkins

9. **Approval Workflow**
   - Regularization goes through approval workflow
   - On submission (after approval), attendance is created automatically
   - See [`attendance_regularization.py`](../hamptons/doctype/attendance_regularization/attendance_regularization.py:32) for submission logic

## Requirements

### Shift Type Configuration

Ensure your Shift Type documents have:
- **Start Time**: Required
- **End Time**: Required
- **Late Entry Grace Period**: Optional (minutes)
- **Working Hours Threshold for Half Day**: Required for proper attendance status calculation

### Attendance Regularization Structure

**Main Document Fields:**
- `employee`: Link to Employee
- `employee_name`: Employee's name
- `posting_date`: Date for the regularization (defaults to today)
- `shift`: Link to Shift Type
- `start_time`: Shift start time
- `end_time`: Shift end time
- `late`: Maximum late time among all checkins
- `status`: Open/Completed
- `attendance`: Link to created Attendance (after approval)
- `reports_to`: Employee's reporting manager

**Child Table (Attendance Regularization Item):**
- `time`: Datetime of checkin
- `log_type`: IN or OUT
- `device_id`: Location/Device identifier
- `employee_checkin`: Link to Employee Checkin document

### Employee Checkin Custom Fields

The system expects these custom fields on Employee Checkin:
- `custom_attendance_regularization`: Link to Attendance Regularization
- `custom_crosschex_uuid`: For CrossChex integration (optional)

### Bios Settings Configuration

Required settings in Bios Settings single DocType:
- **Attendance Regularization Leave Type**: Leave type to use when regularization is rejected
- **Default Leave Type for Half Day**: Leave type for half-day status

## Error Handling

The system includes comprehensive error handling:

1. **Missing Shift Assignment**: Logs error and skips regularization
2. **Invalid Shift Type**: Throws validation error
3. **Shift End Time Not Passed**: Skips regularization with log entry
4. **Duplicate Checkin**: Checks if checkin is already in a regularization item
5. **Submitted Regularization**: Cannot add checkins to submitted/cancelled regularizations
6. **Creation/Update Errors**: Logs errors with full stack trace for debugging

## Logging

All decisions and errors are logged for audit purposes:

- Regularization creation attempts (success/failure)
- Reasons for not creating regularization
- Shift validation errors
- Time calculation results

Check Frappe Error Log for detailed information.

## Testing

To test the system:

1. **Setup Test Data**
   - Create employee with active shift assignment
   - Ensure shift type has valid start/end times and grace period

2. **Test Late Entry (Single Checkin)**
   - Create Employee Checkin with log_type="IN"
   - Set time after shift start + grace period
   - Ensure current time is past shift end time
   - Submit the checkin
   - Verify new attendance regularization is created
   - Verify checkin is in the child table

3. **Test Multiple Late Entries (Same Day)**
   - Create first late checkin and submit
   - Verify regularization is created
   - Create second late checkin for same employee and date
   - Submit second checkin
   - Verify same regularization is updated (not new one created)
   - Verify both checkins are in the child table
   - Verify late time is updated to the maximum

4. **Test Early Exit**
   - Create Employee Checkin with log_type="OUT"
   - Set time before shift end time
   - Ensure current time is past shift end time
   - Submit the checkin
   - Verify attendance regularization is created or updated

5. **Test Grace Period**
   - Create checkin within grace period
   - Verify no regularization is created

6. **Test Before Shift End**
   - Create checkin before shift end time has passed
   - Verify no regularization is created yet

7. **Test Submitted Regularization**
   - Create and submit a regularization
   - Create another late checkin for same employee and date
   - Verify system logs that checkin cannot be added to submitted regularization

## Maintenance

### Common Issues

1. **Regularizations Not Created**
   - Check if shift assignment exists and is active
   - Verify shift type has valid start/end times
   - Ensure current time is past shift end time
   - Check error logs for validation errors

2. **Checkin Not Added to Existing Regularization**
   - Verify regularization is in draft status (docstatus = 0)
   - Check if checkin is already linked to another regularization
   - Review error logs for duplicate checkin attempts

3. **Multiple Regularizations for Same Date**
   - System should consolidate into one draft regularization
   - If multiple exist, check for submitted ones preventing updates
   - Review the posting_date field values

4. **Incorrect Time Calculations**
   - Verify timezone settings in Frappe
   - Check shift type start/end time format
   - Review grace period configuration

### Performance Considerations

- Database queries are optimized with proper indexing
- Only one regularization check per checkin submission
- Bulk operations use efficient SQL queries

## Integration

This system integrates with:

1. **Employee Checkin**: Main trigger point
2. **Shift Assignment**: Source of shift information
3. **Shift Type**: Configuration for timing rules
4. **Attendance Regularization**: Generated documents
5. **Attendance**: Created after regularization approval
6. **Bios Settings**: System configuration

## Key Differences from Previous Version

**Before (One Regularization Per Checkin):**
- Each late/early checkin created a separate regularization document
- Simple one-to-one relationship between checkin and regularization
- Could result in many regularization documents per employee per day

**Now (Consolidated Daily Regularization):**
- One regularization document per employee per day
- Multiple checkins stored in child table
- Reduces document count and simplifies approval workflow
- Better reflects the end-of-day batch processing approach
- Maximum late time tracked across all checkins

## Future Enhancements

Possible improvements:

1. Batch processing of historical checkins
2. Configurable rules per shift type or department
3. SMS/Email notifications for regularization creation
4. Dashboard for regularization statistics
5. Auto-approval for specific scenarios
6. Integration with mobile app for real-time alerts
7. Scheduled job to consolidate checkins at end of shift

## Support

For issues or questions, contact the development team or check:
- Frappe Error Log for detailed error messages
- Database logs for query issues
- System console for real-time debugging

## CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request

## License

MIT
