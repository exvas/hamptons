# Copyright (c) 2025, sammish and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, get_time
from datetime import datetime, timedelta
import re

# Standardize indentation to 4 spaces

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    
    # Add summary row for performance metrics
    summary = get_summary(data) if data else None
    
    return columns, data, None, None, summary

def get_columns():
    return [
        {
            'fieldname': 'date',
            'label': 'Date',
            'fieldtype': 'Date',
        },
        {
            'fieldname': 'employee_id',
            'label': 'Employee ID',
            'fieldtype': 'Link',
            'options': 'Employee',
            'width': 120
        },
        {
            'fieldname': 'employee_name',
            'label': 'Employee Name',
            'fieldtype': 'Data',
            'width': 300
        },
        {
            'fieldname': 'department',
            'label': 'Department',
            'fieldtype': 'Link',
            'options': 'Department',
            'width': 250
        },
        {
            'fieldname': 'status',
            'label': 'Att Code',
            'fieldtype': 'HTML',
            'width': 140
        },
        {
            'fieldname': 'in_time',
            'label': 'In Time',
            'fieldtype': 'Data',
            'width': 90
        },
        {
            'fieldname': 'out_time',
            'label': 'Out Time',
            'fieldtype': 'Data',
            'width': 90
        },
        {
            'fieldname': 'base_hours',
            'label': 'Base Hrs',
            'fieldtype': 'Duration',
            'width': 90
        },
        {
            'fieldname': 'total_working_hours',
            'label': 'Work Hrs',
            'fieldtype': 'Duration',
            'width': 90
        },
        {
            'fieldname': 'ot1',
            'label': 'OT',
            'fieldtype': 'Duration',
            'width': 100
        },
        {
            'fieldname': 'ut',
            'label': 'UT',
            'fieldtype': 'Duration',
            'width': 90
        },
        {
            'fieldname': 'early_exit',
            'label': 'Early Exit',
            'fieldtype': 'Check',
            'width': 90
        },
        {
            'fieldname': 'late_entry',
            'label': 'Late Entry',
            'fieldtype': 'Check',
            'width': 90
        },
        {
            'fieldname': 'attendance_reference',
            'label': 'Attendance Ref.',
            'fieldtype': 'Link',
            'options': 'Attendance',
            'width': 150
        },
        {
            'fieldname': 'employee_checkin_references',
            'label': 'Checkin Refs.',
            'fieldtype': 'Data',
            'width': 200
        }
    ]

def recalculate_working_hours_from_checkins(attendance_reference):
    """
    Recalculate working hours from employee checkins when break hours are negative
    This provides a fallback calculation method for corrupted break hour data
    """
    if not attendance_reference:
        return None
        
    try:
        # Get employee checkins for this attendance record
        checkins = frappe.db.sql("""
            SELECT
                check_in,
                check_out
            FROM `tabEmployee Checkin List`
            WHERE parent = %s AND check_in IS NOT NULL
            ORDER BY check_in
        """, (attendance_reference,), as_dict=True)
        
        if not checkins:
            return None
            
        total_working_seconds = 0
        total_break_seconds = 0
        
        for i, checkin in enumerate(checkins):
            if checkin.check_out:
                # Calculate working time for this check-in/check-out pair
                check_in_time = checkin.check_in
                check_out_time = checkin.check_out
                
                # Ensure they are datetime objects
                if isinstance(check_in_time, str):
                    check_in_time = datetime.strptime(check_in_time, '%Y-%m-%d %H:%M:%S')
                if isinstance(check_out_time, str):
                    check_out_time = datetime.strptime(check_out_time, '%Y-%m-%d %H:%M:%S')
                
                working_seconds = (check_out_time - check_in_time).total_seconds()
                if working_seconds > 0:
                    total_working_seconds += working_seconds
                
                # Calculate break time between this check-out and next check-in
                if i < len(checkins) - 1 and checkins[i + 1].check_in:
                    next_check_in = checkins[i + 1].check_in
                    if isinstance(next_check_in, str):
                        next_check_in_time = datetime.strptime(next_check_in, '%Y-%m-%d %H:%M:%S')
                    else:
                        next_check_in_time = next_check_in
                    break_seconds = (next_check_in_time - check_out_time).total_seconds()
                    if break_seconds > 0:
                        total_break_seconds += break_seconds
        
        return {
            'working_hours': total_working_seconds,
            'break_hours': total_break_seconds,
            'checkin_count': len(checkins)
        }
        
    except Exception as e:
        frappe.log_error(f"Error recalculating working hours: {str(e)}")
        return None

def get_data(filters):
    # Ensure filters is a frappe._dict
    if not isinstance(filters, frappe._dict):
        filters = frappe._dict(filters or {})
    
    # Enhanced filter value cleaning
    for key in list(filters.keys()):
        value = filters[key]
        if isinstance(value, str):
            # More robust cleaning for date fields
            if key in ['from_date', 'to_date']:
                # Remove any trailing %, whitespaces, or other non-date characters
                cleaned_value = ''.join(c for c in value if c in '0123456789-')
                
                try:
                    # Attempt to parse and standardize date
                    from datetime import datetime
                    parsed_date = datetime.strptime(cleaned_value, '%Y-%m-%d').strftime('%Y-%m-%d')
                    filters[key] = parsed_date
                except (ValueError, TypeError):
                    frappe.logger().warning(f"Invalid date format for {key}: {cleaned_value}")
                    # Remove invalid date filter
                    del filters[key]
            else:
                # Standard cleaning for non-date fields
                filters[key] = value.rstrip('%').rstrip().rstrip('*')
    
    # Validate required filters
    if not filters.get('from_date'):
        frappe.throw("From Date is required")
    if not filters.get('to_date'):
        frappe.throw("To Date is required")
    
    # Get all employees based on filters
    employee_query = "SELECT name as employee_id, employee_name, department FROM `tabEmployee` WHERE status = 'Active'"
    params = []
    if filters.get('employee_id'):
        employee_query += " AND name = %s"
        params.append(filters.get('employee_id'))
    if filters.get('department'):
        employee_query += " AND department = %s"
        params.append(filters.get('department'))
    
    employees = frappe.db.sql(employee_query, tuple(params) if params else (), as_dict=True)
    if not employees:
        return []
    
    # Hybrid approach: Get attendance status from Attendance table, times from Employee Checkin
    # First, get attendance records with their status
    attendance_query = """
        SELECT
            a.attendance_date as date,
            a.employee as employee_id,
            e.employee_name as employee_name,
            e.department as department,
            a.in_time as att_in_time,
            a.out_time as att_out_time,
            a.status as original_status,
            a.leave_type as attendance_leave_type,
            a.name as attendance_reference,
            a.late_entry,
            a.early_exit,
            a.working_hours as att_working_hours
        FROM `tabAttendance` a
        LEFT JOIN `tabEmployee` e ON a.employee = e.name
        WHERE a.attendance_date BETWEEN %s AND %s
        AND a.docstatus = 1
    """

    att_params = [filters.from_date, filters.to_date]
    if filters.get('employee_id'):
        attendance_query += " AND a.employee = %s"
        att_params.append(filters.get('employee_id'))

    if filters.get('department'):
        attendance_query += " AND e.department = %s"
        att_params.append(filters.get('department'))

    attendance_records = frappe.db.sql(attendance_query, tuple(att_params), as_dict=True)

    # Create attendance lookup by employee and date
    attendance_status_lookup = {}
    for att in attendance_records:
        key = f"{att['employee_id']}_{att['date']}"
        attendance_status_lookup[key] = att

    # Get earliest check-in and latest check-out per employee per day from Employee Checkin
    # Include both draft (docstatus=0) and submitted (docstatus=1) checkins
    query = """
        WITH checkin_data AS (
            SELECT
                DATE(time) as date,
                employee,
                time,
                log_type,
                name as checkin_name,
                COUNT(*) OVER (PARTITION BY DATE(time), employee) as checkin_count,
                ROW_NUMBER() OVER (PARTITION BY DATE(time), employee ORDER BY time) as checkin_order,
                ROW_NUMBER() OVER (PARTITION BY DATE(time), employee ORDER BY time DESC) as reverse_order
            FROM `tabEmployee Checkin`
            WHERE DATE(time) BETWEEN %s AND %s
        )
        SELECT
            cd.date,
            cd.employee as employee_id,
            e.employee_name as employee_name,
            e.department as department,
            -- In Time: First check-in of the day
            MIN(CASE WHEN cd.checkin_order = 1 THEN cd.time END) as in_time,
            -- Out Time: Only if there are multiple check-ins, otherwise NULL
            CASE
                WHEN cd.checkin_count > 1 THEN MAX(CASE WHEN cd.reverse_order = 1 THEN cd.time END)
                ELSE NULL
            END as out_time,
            -- Working hours: Only calculate if both in and out times exist
            CASE
                WHEN cd.checkin_count > 1 THEN
                    TIMESTAMPDIFF(SECOND,
                        MIN(CASE WHEN cd.checkin_order = 1 THEN cd.time END),
                        MAX(CASE WHEN cd.reverse_order = 1 THEN cd.time END)
                    )
                ELSE 0
            END as original_working_hours,
            0 as late_entry,
            0 as early_exit,
            NULL as original_status,
            '' as attendance_leave_type,
            '' as attendance_reference,
            0 as ot1,
            0 as ot2,
            0 as ut,
            GROUP_CONCAT(DISTINCT cd.checkin_name ORDER BY cd.time) as employee_checkin_references
        FROM checkin_data cd
        LEFT JOIN `tabEmployee` e ON cd.employee = e.name
    """

    if filters.get('employee_id'):
        query += " AND cd.employee = %s"

    if filters.get('department'):
        query += " AND e.department = %s"

    query += " GROUP BY cd.date, cd.employee, e.employee_name, e.department, cd.checkin_count ORDER BY cd.employee, cd.date"
    
    # Build parameters list
    params = [filters.from_date, filters.to_date]
    if filters.get('employee_id'):
        params.append(filters.get('employee_id'))
    if filters.get('department'):
        params.append(filters.get('department'))
    
    existing_attendance = frappe.db.sql(query, tuple(params), as_dict=True)
    
    # Create a comprehensive data structure with all dates for each employee
    # Ensure filters are strings and strip any whitespace
    from_date_str = str(filters.from_date).strip() if filters.from_date else None
    to_date_str = str(filters.to_date).strip() if filters.to_date else None
    start_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
    
    data = []
    
    # Create checkin lookup for existing records (from Employee Checkin)
    checkin_lookup = {}
    for record in existing_attendance:
        key = f"{record['employee_id']}_{record['date']}"
        # Convert datetime to time string format (HH:MM AM/PM)
        # Use frappe.utils.get_time to safely extract time

        if record['in_time']:
            try:
                in_time_obj = get_time(record['in_time'])
                record['in_time'] = in_time_obj.strftime('%I:%M %p')
            except Exception as e:
                frappe.logger().error(f"Error converting in_time: {str(e)}")
                record['in_time'] = ''

        if record['out_time']:
            try:
                out_time_obj = get_time(record['out_time'])
                # Only set out_time if it's different from in_time
                if out_time_obj != get_time(record['in_time']):
                    record['out_time'] = out_time_obj.strftime('%I:%M %p')
                else:
                    record['out_time'] = ''
            except Exception as e:
                frappe.logger().error(f"Error converting out_time: {str(e)}")
                record['out_time'] = ''

        # Merge with attendance status if available
        if key in attendance_status_lookup:
            att_record = attendance_status_lookup[key]
            record['original_status'] = att_record['original_status']
            record['attendance_leave_type'] = att_record['attendance_leave_type'] or ''
            # Combine attendance references if multiple exist
            if att_record['attendance_reference']:
                # If there are multiple attendance references, join with comma
                existing_ref = record.get('attendance_reference', '')
                if existing_ref and existing_ref != att_record['attendance_reference']:
                    record['attendance_reference'] = f"{existing_ref}, {att_record['attendance_reference']}"
                else:
                    record['attendance_reference'] = att_record['attendance_reference']
            record['late_entry'] = att_record.get('late_entry', 0)
            record['early_exit'] = att_record.get('early_exit', 0)
            # Use working hours from Attendance if available
            if att_record.get('att_working_hours'):
                record['original_working_hours'] = float(att_record['att_working_hours']) * 3600  # Convert hours to seconds

        # Ensure employee_checkin_references field exists
        if 'employee_checkin_references' not in record:
            record['employee_checkin_references'] = ''

        checkin_lookup[key] = record

    # Also add attendance records that don't have checkins (for On Leave, etc.)
    for key, att_record in attendance_status_lookup.items():
        if key not in checkin_lookup:
            # Create record from attendance without checkin times
            in_time_str = ''
            out_time_str = ''
            if att_record.get('att_in_time'):
                try:
                    in_time_obj = get_time(att_record['att_in_time'])
                    in_time_str = in_time_obj.strftime('%I:%M %p')
                except:
                    pass
            if att_record.get('att_out_time'):
                try:
                    out_time_obj = get_time(att_record['att_out_time'])
                    # Only set out_time if it's different from in_time
                    if att_record.get('att_in_time'):
                        in_time_obj = get_time(att_record['att_in_time'])
                        if out_time_obj != in_time_obj:
                            out_time_str = out_time_obj.strftime('%I:%M %p')
                        else:
                            out_time_str = ''
                    else:
                        out_time_str = out_time_obj.strftime('%I:%M %p')
                except:
                    out_time_str = ''

            checkin_lookup[key] = {
                'date': att_record['date'],
                'employee_id': att_record['employee_id'],
                'employee_name': att_record['employee_name'],
                'department': att_record['department'],
                'in_time': in_time_str,
                'out_time': out_time_str,
                'original_working_hours': float(att_record.get('att_working_hours') or 0) * 3600,
                'late_entry': att_record.get('late_entry', 0),
                'early_exit': att_record.get('early_exit', 0),
                'original_status': att_record['original_status'],
                'attendance_leave_type': att_record['attendance_leave_type'] or '',
                'attendance_reference': att_record['attendance_reference'] or '',
                'ot1': 0,
                'ot2': 0,
                'ut': 0,
                'employee_checkin_references': ''  # Add empty checkin references
            }
    
    # Generate all employees and dates combinations - Group by Employee
    for employee in employees:
        current_date = start_date
        while current_date <= end_date:
            key = f"{employee['employee_id']}_{current_date}"

            if key in checkin_lookup:
                # Use existing record from check-ins merged with attendance
                row = checkin_lookup[key]
            else:
                # Create placeholder record for date with no check-ins
                row = {
                    'date': current_date,
                    'employee_id': employee['employee_id'],
                    'employee_name': employee['employee_name'],
                    'department': employee['department'],
                    'in_time': '',
                    'out_time': '',
                    'base_hours': 0,
                    'original_working_hours': 0,
                    'break_hours': 0,
                    'late_entry': 0,
                    'early_exit': 0,
                    'original_status': None,
                    'attendance_leave_type': '',
                    'attendance_reference': '',
                    'employee_checkin_references': '',  # Add new field
                    'ot1': 0,
                    'ot2': 0,
                    'ut': 0
                }
            
            data.append(row)
            current_date += timedelta(days=1)
    
    # Get all leave applications for the date range to match with attendance
    leave_applications = {}
    # Get all holidays for employees in the date range
    employee_holidays = {}
    # Get all week-off days for employees based on shift policy
    employee_weekoffs = {}
    # Get base hours from shift policies for employees
    employee_base_hours = {}
    # Create optimized lookup dictionaries for holidays and leave applications by date
    holiday_lookup = {}  # Format: (emp_id, date) -> True
    leave_lookup = {}    # Format: (emp_id, date) -> leave_type
    weekoff_lookup = {}   # Format: (emp_id, day_name) -> True
    
    if data:
        employees_list = list(set([row['employee_id'] for row in data]))
        placeholders = ','.join(['%s'] * len(employees_list))
        leave_apps = frappe.db.sql(f"""
            SELECT
                employee as employee_id,
                from_date,
                to_date,
                leave_type
            FROM `tabLeave Application`
            WHERE employee IN ({placeholders})
            AND docstatus = 1
            AND from_date <= %s
            AND to_date >= %s
        """, employees_list + [filters.to_date, filters.from_date], as_dict=True)
        
        # Create optimized lookup dictionaries for leave applications
        for la in leave_apps:
            emp_id = la.employee_id
            # Store in both formats: by employee (for backward compatibility) and by date (for O(1) lookup)
            if emp_id not in leave_applications:
                leave_applications[emp_id] = []
            leave_applications[emp_id].append(la)
            
            # Create date-based lookup for O(1) access during row processing
            current_date = la.from_date
            while current_date <= la.to_date:
                leave_lookup[(emp_id, current_date)] = la.leave_type
                current_date += timedelta(days=1)
        
        # Get holiday lists for all employees (using tabHoliday which is the correct child table)
        try:
            placeholders = ','.join(['%s'] * len(employees_list))
            holiday_data = frappe.db.sql(f"""
                SELECT
                    e.name as employee_id,
                    h.holiday_date,
                    h.description,
                    h.weekly_off
                FROM `tabEmployee` e
                LEFT JOIN `tabHoliday List` hl ON e.holiday_list = hl.name
                LEFT JOIN `tabHoliday` h ON hl.name = h.parent
                WHERE e.name IN ({placeholders})
                AND h.holiday_date BETWEEN %s AND %s
            """, employees_list + [filters.from_date, filters.to_date], as_dict=True)

            # Create lookup dictionaries for holidays and weekly offs from holiday list
            for holiday in holiday_data:
                emp_id = holiday.employee_id
                holiday_date = holiday.holiday_date

                if emp_id not in employee_holidays:
                    employee_holidays[emp_id] = []
                employee_holidays[emp_id].append(holiday)

                # Add to holiday lookup for O(1) access
                holiday_lookup[(emp_id, holiday_date)] = True

                # If this is a weekly_off day, also add to weekoff_lookup
                # This catches Friday/Saturday marked as weekly_off in Holiday List
                if holiday.weekly_off == 1:
                    day_name = holiday_date.strftime('%A')
                    weekoff_lookup[(emp_id, day_name)] = True
        except Exception as e:
            # If Holiday table query fails, log error and continue without holidays
            frappe.log_error(f"Error fetching holiday data: {str(e)}")
            employee_holidays = {}
        
        # Get shift assignments, week-off days, and base hours for employees
        try:
            placeholders = ','.join(['%s'] * len(employees_list))
            shift_assignment_data = frappe.db.sql(f"""
                SELECT
                    sa.employee as employee_id,
                    sa.shift_type as shift_policy,
                    sa.start_date as from_date,
                    sa.modified as assignment_modified,
                    eo.days as week_off_day,
                    eo.base_hours,
                    eo.work_days,
                    eo.day_off
                FROM `tabShift Assignment` sa
                LEFT JOIN `tabShift Type` sp ON sa.shift_type = sp.name
                LEFT JOIN `tabEmployee Overtime` eo ON sp.name = eo.parent
                WHERE sa.employee IN ({placeholders})
                AND sa.docstatus = 1
                AND sa.start_date <= %s
                ORDER BY sa.employee, sa.start_date DESC
            """, employees_list + [filters.to_date], as_dict=True)
            
            # Create lookup dictionaries for week-off days and base hours per employee
            employee_weekoffs = {}
            employee_base_hours = {}
            
            for shift_data in shift_assignment_data:
                emp_id = shift_data.employee_id
                
                # Handle week-off days (day_off = 1)
                if emp_id not in employee_weekoffs:
                    employee_weekoffs[emp_id] = []
                if shift_data.week_off_day and shift_data.day_off == 1:
                    employee_weekoffs[emp_id].append({
                        'week_off_day': shift_data.week_off_day,
                        'from_date': shift_data.from_date
                    })
                    # Create day-name based lookup for O(1) access during row processing
                    weekoff_lookup[(emp_id, shift_data.week_off_day)] = True
                
                # Handle base hours for work days (work_days = 1)
                if emp_id not in employee_base_hours:
                    employee_base_hours[emp_id] = []
                if shift_data.base_hours and shift_data.work_days == 1:
                    employee_base_hours[emp_id].append({
                        'day': shift_data.week_off_day,  # This contains the day name
                        'base_hours': shift_data.base_hours,
                        'from_date': shift_data.from_date,
                        'assignment_modified': shift_data.assignment_modified
                    })
        except Exception as e:
            # If shift assignment query fails, log error and continue with empty shift data
            frappe.log_error(f"Error fetching shift assignment data: {str(e)}")
            employee_weekoffs = {}
            employee_base_hours = {}
    
    # Get standard working hours from HR Settings (in hours)
    standard_working_hours = frappe.db.get_single_value('HR Settings', 'standard_working_hours') or 8
    standard_working_hours_seconds = int(standard_working_hours * 3600)  # Convert to seconds
    
    # Process each record to set proper status and leave_type
    # Enhanced logic to handle negative break hours and recalculate working time
    for row in data:
        # Fix working hours calculation - ensure proper conversion and validation
        work_hours_seconds = row.get('original_working_hours', 0) or 0
        break_hours_seconds = 0  # No break hours available from query, will be set to 0
        
        # Enhanced logic to handle break hours calculations intelligently
        original_break_hours = break_hours_seconds
        
        # Validate and convert working hours (handle corrupted data)
        if isinstance(work_hours_seconds, (int, float)):
            # Check for unreasonable values (more than 24 hours = 86400 seconds or negative values)
            if work_hours_seconds > 86400 or work_hours_seconds < 0:
                work_hours_seconds = 0  # Reset corrupted data
            else:
                work_hours_seconds = int(work_hours_seconds)
        else:
            work_hours_seconds = 0
            
        # Enhanced break hours validation with negative handling
        if isinstance(break_hours_seconds, (int, float)):
            # If break hours are negative, it indicates a calculation error
            if break_hours_seconds < 0:
                # Store the negative value for reference but don't use in calculations
                row['original_break_hours'] = break_hours_seconds
                
                # Try to recalculate from employee checkins first (most accurate)
                recalculated = None
                if row.get('attendance_reference'):
                    recalculated = recalculate_working_hours_from_checkins(row['attendance_reference'])
                
                if recalculated and recalculated['working_hours'] > 0:
                    # Use recalculated values from employee checkins
                    work_hours_seconds = int(recalculated['working_hours'])
                    break_hours_seconds = int(recalculated['break_hours'])
                    row['break_hours_note'] = f"Recalculated from {recalculated['checkin_count']} check-ins (was {original_break_hours/3600:.2f}h)"
                elif row.get('in_time') and row.get('out_time'):
                    # Fallback: calculate from in/out time
                    try:
                        # Parse time strings to calculate total duration
                        in_time_str = str(row.get('in_time', ''))
                        out_time_str = str(row.get('out_time', ''))
                        
                        # Try to calculate from in/out time if available
                        if in_time_str and out_time_str and in_time_str != '' and out_time_str != '':
                            # Assume same date for calculation
                            date_str = str(row.get('date', '2025-01-01'))
                            in_datetime = datetime.strptime(f"{date_str} {in_time_str}", "%Y-%m-%d %I:%M %p")
                            out_datetime = datetime.strptime(f"{date_str} {out_time_str}", "%Y-%m-%d %I:%M %p")
                            
                            # Handle overnight shifts
                            if out_datetime < in_datetime:
                                out_datetime += timedelta(days=1)
                            
                            calculated_working_seconds = (out_datetime - in_datetime).total_seconds()
                            
                            # Use calculated time if it's reasonable
                            if 0 <= calculated_working_seconds <= 86400:  # 0-24 hours
                                work_hours_seconds = int(calculated_working_seconds)
                                break_hours_seconds = 0  # Can't calculate breaks from simple in/out
                                row['break_hours_note'] = f"Calculated from in/out time (was {original_break_hours/3600:.2f}h)"
                    except (ValueError, TypeError):
                        # If time parsing fails, keep original working hours but reset breaks
                        break_hours_seconds = 0
                        row['break_hours_note'] = f"Break hours reset (was {original_break_hours/3600:.2f}h)"
                else:
                    # No way to recalculate, just reset break hours
                    break_hours_seconds = 0
                    row['break_hours_note'] = f"Break hours reset (was {original_break_hours/3600:.2f}h)"
            elif break_hours_seconds > 86400:  # More than 24 hours
                break_hours_seconds = 0  # Reset corrupted data
            else:
                break_hours_seconds = int(break_hours_seconds)
        else:
            break_hours_seconds = 0
        
        # Final working hours and break hours assignment
        row['total_working_hours'] = work_hours_seconds
        row['break_hours'] = break_hours_seconds
        
        # Add a flag to indicate if break hours were corrected
        if original_break_hours < 0:
            row['break_hours_corrected'] = True
            # Only set the note if it hasn't been set already by the recalculation logic
            if not row.get('break_hours_note'):
                row['break_hours_note'] = f"Original: {original_break_hours/3600:.2f}h (corrected to 0)"
        else:
            row['break_hours_corrected'] = False
            
        # Additional validation: Check if working hours seem unreasonably low compared to in/out time
        if (work_hours_seconds > 0 and work_hours_seconds < 7200 and  # Less than 2 hours
            row.get('in_time') and row.get('out_time') and
            row.get('in_time') != row.get('out_time')):
            
            # Add a warning note for suspiciously low working hours
            current_note = row.get('break_hours_note', '')
            if current_note:
                row['break_hours_note'] = current_note + " | Low working hours detected"
            else:
                row['break_hours_note'] = "Warning: Working hours seem low - verify attendance data"
        
        # Calculate and set base hours from shift policy, fallback to standard working hours
        base_hours_from_shift = get_employee_base_hours_for_date(
            row['employee_id'],
            row['date'],
            employee_base_hours
        )
        # Use shift-based base hours if available, otherwise use standard working hours
        row['base_hours'] = base_hours_from_shift if base_hours_from_shift > 0 else standard_working_hours_seconds
        
        # Calculate OT1 and UT based on working hours vs base hours
        base_hours_seconds = row['base_hours']
        working_hours_seconds = row['total_working_hours']
        
        # Only calculate OT1 and UT for working days (not holidays, week-offs, leaves)
        if (row.get('original_status') == 'Present' and 
            base_hours_seconds > 0 and 
            working_hours_seconds > 0):
            
            if working_hours_seconds > base_hours_seconds:
                # Overtime: working hours exceed base hours
                row['ot1'] = working_hours_seconds - base_hours_seconds
                row['ut'] = 0
            elif working_hours_seconds < base_hours_seconds:
                # Under time: working hours less than base hours
                row['ut'] = base_hours_seconds - working_hours_seconds
                row['ot1'] = 0
            else:
                # Exact match
                row['ot1'] = 0
                row['ut'] = 0
        else:
            # For non-working days, holidays, leaves, etc.
            row['ot1'] = 0
            row['ut'] = 0
        
        # First check if the date is a holiday for this employee - O(1) lookup instead of iteration
        is_holiday_date = (row['employee_id'], row['date']) in holiday_lookup
        
        # Check if the date is a week-off day based on shift policy - O(1) lookup instead of iteration
        row_weekday = row['date'].strftime('%A')  # Get day name (Monday, Tuesday, etc.)
        is_week_off = (row['employee_id'], row_weekday) in weekoff_lookup
        
        # Priority order: Check for both Holiday and Week Off combinations
        if is_holiday_date and is_week_off:
            # When both holiday and week-off, show "Week Off (Holiday)"
            row['status'] = format_attendance_status('Week Off (Holiday)')
            row['leave_type'] = ''
            # Keep punch data for Week Off (Holiday) records - don't clear them
            row['total_working_hours'] = 0
            row['base_hours'] = 0
        elif is_holiday_date:
            # Show holiday with original status if there's punch data
            if row['original_status'] in ['Present', 'On Leave', 'Absent']:
                original_status = row['original_status']
                if original_status == 'Present':
                    display_status = 'Present'
                elif original_status == 'Absent':
                    display_status = 'Absent'
                else:
                    display_status = original_status
                
                # Show Holiday with punch status if punch times exist
                if row['in_time'] or row['out_time']:
                    row['status'] = format_attendance_status(f'Holiday ({display_status})')
                else:
                    row['status'] = format_attendance_status('Holiday')
            else:
                # No attendance record for holiday, just mark as Holiday
                row['status'] = format_attendance_status('Holiday')
            row['leave_type'] = ''
        elif is_week_off:
            # Mark as "Week Off" regardless of whether attendance is marked or not
            row['status'] = format_attendance_status('Week Off')
            row['leave_type'] = ''
            # Keep punch data for Week Off records - don't clear them
            row['total_working_hours'] = 0
            row['base_hours'] = 0
        # Otherwise, determine the final status and leave_type normally
        elif row['original_status'] == 'Present':
            # Present with only IN time (no OUT) is actually a Mis-Punch
            if row.get('in_time') and not row.get('out_time'):
                row['status'] = format_attendance_status('Mis-Punch')
            else:
                row['status'] = format_attendance_status('PR')
            row['leave_type'] = ''
        elif row['original_status'] == 'On Leave':
            # Try to find leave type from attendance first
            leave_type_found = None
            if row['attendance_leave_type'] and row['attendance_leave_type'].strip():
                leave_type_found = row['attendance_leave_type'].strip()
            else:
                # Look for leave application - O(1) lookup instead of iteration
                leave_type_found = leave_lookup.get((row['employee_id'], row['date']))
            
            if leave_type_found:
                row['status'] = format_attendance_status(leave_type_found)
                row['leave_type'] = leave_type_found
            else:
                row['status'] = format_attendance_status('On Leave')
                row['leave_type'] = ''
        elif row['original_status'] is None:
            # No attendance record - check if there's a leave application for this date - O(1) lookup
            leave_type_found = leave_lookup.get((row['employee_id'], row['date']))

            if leave_type_found:
                row['status'] = format_attendance_status(leave_type_found)
                row['leave_type'] = leave_type_found
            else:
                # Check if there are checkins but no attendance (pending consolidation)
                has_checkins = row.get('in_time') or row.get('employee_checkin_references')
                if has_checkins:
                    # Has checkins but no attendance record yet - mark as Pending
                    row['status'] = format_attendance_status('Pending')
                    row['leave_type'] = ''
                    # Clear out_time if it's the same as in_time (single checkin)
                    if row.get('in_time') and row.get('out_time') and row.get('in_time') == row.get('out_time'):
                        row['out_time'] = ''
                else:
                    # No checkins and no leave application, mark as Absent
                    row['status'] = format_attendance_status('Absent')
                    row['leave_type'] = ''
        else:
            # For other statuses (Absent, etc.)
            if row['attendance_leave_type'] and row['attendance_leave_type'].strip():
                row['leave_type'] = row['attendance_leave_type'].strip()
            else:
                row['leave_type'] = ''
            # Distinguish Absent with in_time (mis-punch / missing checkout) from true Absent
            if row['original_status'] == 'Absent' and row.get('in_time'):
                row['status'] = format_attendance_status('Mis-Punch')
            else:
                row['status'] = format_attendance_status(row['original_status'] or 'Absent')
    
    # Apply att_code filter if provided
    if filters.get('att_code'):
        att_code_filter = filters.get('att_code').strip()
        # Filter by checking if the att_code appears in the status HTML or plain status
        filtered_data = []
        for row in data:
            status = str(row.get('status', ''))
            # Extract plain text from HTML if needed - re already imported at top
            plain_status = re.sub(r'<[^>]+>', '', status)  # Remove HTML tags
            plain_status = plain_status.strip()
            # Check both HTML and plain text
            if (att_code_filter.lower() in status.lower() or
                att_code_filter.lower() in plain_status.lower()):
                filtered_data.append(row)
        data = filtered_data
    
    return data


def get_employee_base_hours_for_date(employee_id, attendance_date, employee_base_hours):
    """
    Get the base hours for an employee on a specific date based on their shift policy assignment.
    Validates the shift assignment date against the attendance date.
    """
    if employee_id not in employee_base_hours:
        return 0
    
    # Get the day name for the attendance date
    day_name = attendance_date.strftime('%A')
    
    # Find the most recent shift assignment that applies to this date
    applicable_base_hours = None
    for base_hour_data in employee_base_hours[employee_id]:
        # Check if this shift assignment applies to the attendance date
        if base_hour_data['from_date'] <= attendance_date:
            # Check if this day matches the attendance day
            if base_hour_data['day'] == day_name:
                if applicable_base_hours is None or base_hour_data['from_date'] > applicable_base_hours['from_date']:
                    applicable_base_hours = base_hour_data
    
    if applicable_base_hours:
        # Convert float hours to seconds (Frappe duration format)
        base_hours_float = applicable_base_hours['base_hours']
        return int(base_hours_float * 3600)  # Convert hours to seconds
    
    return 0


def format_attendance_status(status):
    """
    Format attendance status with colors and bold text
    """
    if not status:
        return status
        
    color_map = {
        'Week Off': '<span style="color: blue; font-weight: bold;">Week Off</span>',
        'Week Off (Holiday)': '<span style="color: blue; font-weight: bold;">Week Off (Holiday)</span>',
        'PR': '<span style="color: green; font-weight: bold;">Present</span>',
        'Present': '<span style="color: green; font-weight: bold;">Present</span>',
        'Absent': '<span style="color: red; font-weight: bold;">Absent</span>',
        'Pending': '<span style="color: orange; font-weight: bold;">Pending</span>',
        'Holiday': '<span style="color: purple; font-weight: bold;">Holiday</span>',
        'Mis-Punch': '<span style="color: orange; font-weight: bold;">Mis-Punch</span>',
        'On Leave': '<span style="color: blue; font-weight: bold;">On Leave</span>',
        'Half Day': '<span style="color: #FF6600; font-weight: bold;">Half Day</span>',
        'Work From Home': '<span style="color: #0099CC; font-weight: bold;">Work From Home</span>'
    }
    
    # Handle Holiday with punch status (e.g., "Holiday (Present)")
    if status.startswith('Holiday (') and status.endswith(')'):
        return f'<span style="color: purple; font-weight: bold;">{status}</span>'
    
    # Check if status is a leave type (not in predefined statuses)
    if status not in color_map:
        # Assume it's a leave type, color it blue
        return f'<span style="color: blue; font-weight: bold;">{status}</span>'
    
    return color_map.get(status, status)


def get_common_week_leave(shift_manager, is_flexible_shift):
    if is_flexible_shift:
        return [day.days for day in frappe.get_all(
            "Employee Overtime",
            filters={"parent": shift_manager, "day_off": 1},
            fields=["days"]
        )]
    else:
        return [day.days for day in frappe.get_all(
            "Shift Manager List",
            filters={"parent": shift_manager, "work_days": 0},
            fields=["days"]
        )]
def is_holiday(date, employee):
    try:
        holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
        if not holiday_list:
            return False
        else:
            holidays = frappe.get_all(
                "Holiday List Entry",
                filters={"parent": holiday_list},
                fields=["start_date", "end_date"]
            )
            for holiday in holidays:
                if date >= holiday.start_date and date <= holiday.end_date:
                    return True
            return False
    except Exception as e:
        frappe.log_error(f"Error checking holiday: {str(e)}")
        return False

def get_summary(data):
    """Generate summary statistics for the report"""
    if not data:
        return []

    total_records = len(data)
    # Count Week Off and Week Off (Holiday) together - check for HTML content
    week_off_count = len([d for d in data if 'Week Off' in str(d.get("status", ""))])
    # Count Present records - check for both PR and Present in HTML content
    present_count = len([d for d in data if 'Present' in str(d.get("status", ""))])
    # Count Absent records - exclude Week Off and Mis-Punch
    absent_count = len([d for d in data if 'Absent' in str(d.get("status", "")) and 'Week Off' not in str(d.get("status", ""))])
    # Count Holiday and Holiday with punch status, but exclude Week Off (Holiday) as it's counted in week_off_count
    holiday_count = len([d for d in data if 'Holiday' in str(d.get("status", "")) and 'Week Off' not in str(d.get("status", ""))])
    # Count Mis-Punch (Absent with in_time - missing checkout)
    mis_punch_count = len([d for d in data if 'Mis-Punch' in str(d.get("status", ""))])
    # Count Pending (checkins exist but no Attendance record yet)
    pending_count = len([d for d in data if 'Pending' in str(d.get("status", ""))])

    return [
        {
            "label": "Total Records",
            "value": total_records,
            "indicator": "Blue"
        },
        {
            "label": "Week Off",
            "value": week_off_count,
            "indicator": "Orange"
        },
        {
            "label": "Present",
            "value": present_count,
            "indicator": "Green"
        },
        {
            "label": "Holiday",
            "value": holiday_count,
            "indicator": "Purple"
        },
        {
            "label": "Mis-Punch",
            "value": mis_punch_count,
            "indicator": "Orange"
        },
        {
            "label": "Pending",
            "value": pending_count,
            "indicator": "Yellow"
        },
        {
            "label": "Absent",
            "value": absent_count,
            "indicator": "Red"
        }
    ]

def test_consolidate_attendance():
    filters = {'from_date': '2025-11-01', 'to_date': '2025-11-30'}
    try:
        data = get_data(filters)
        print(f'Got {len(data)} records')
        if data:
            print('First record:')
            for key, value in data[0].items():
                print(f'  {key}: {value}')
    except Exception as e:
        print(f'Error: {e}')

# Uncomment the following line to run the test when this script is executed directly
# test_consolidate_attendance()

def test_report_via_console():
    """
    Run this function from Frappe console to test the report:
    bench --site [site-name] console
    >>> from hamptons.hamptons.report.consolidate_attendance.consolidate_attendance import test_report_via_console
    >>> test_report_via_console()
    """
    filters = {'from_date': '2025-11-01', 'to_date': '2025-11-30'}
    try:
        data = get_data(filters)
        print(f'=== Consolidate Attendance Report Test ===')
        print(f'Total records: {len(data)}')
        if data:
            print(f'\nFirst 5 records:')
            for i, row in enumerate(data[:5]):
                print(f'\nRecord {i+1}:')
                print(f'  Date: {row.get("date")}')
                print(f'  Employee: {row.get("employee_id")} - {row.get("employee_name")}')
                print(f'  In Time: {row.get("in_time")}')
                print(f'  Out Time: {row.get("out_time")}')
                print(f'  Status: {row.get("status")}')
                print(f'  Working Hours: {row.get("total_working_hours")} seconds')
        
        # Check for blank times
        blank_in_time = sum(1 for row in data if row.get('in_time') == '')
        blank_out_time = sum(1 for row in data if row.get('out_time') == '')
        print(f'\n=== Summary ===')
        print(f'Records with blank In Time: {blank_in_time}')
        print(f'Records with blank Out Time: {blank_out_time}')
        
        if blank_in_time > 0 or blank_out_time > 0:
            print(f'\n=== WARNING: Some records have blank times ===')
            for i, row in enumerate(data):
                if row.get('in_time') == '' or row.get('out_time') == '':
                    print(f'Record {i}: Employee {row.get("employee_id")} on {row.get("date")} - In: {row.get("in_time")}, Out: {row.get("out_time")}')
        
        return data
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
        return None
