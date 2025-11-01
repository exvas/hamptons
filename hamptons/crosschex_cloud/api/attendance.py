import frappe
import json
from datetime import datetime

logMap = {
    0: "IN",
    1: "OUT",
    128: "IN",
    129: "OUT"
}

def debug_table_structure():
    """Debug function to check Employee Checkin table structure"""
    try:
        columns = frappe.db.sql("DESCRIBE `tabEmployee Checkin`", as_dict=True)
        frappe.log_error(
            message=f"Employee Checkin table structure: {json.dumps(columns, indent=2)}",
            title="CrossChex Debug - Employee Checkin Table"
        )
        
        # Also check Attendance table structure
        att_columns = frappe.db.sql("DESCRIBE `tabAttendance`", as_dict=True)
        frappe.log_error(
            message=f"Attendance table structure: {json.dumps(att_columns, indent=2)}",
            title="CrossChex Debug - Attendance Table"
        )
        
        return columns
    except Exception as e:
        frappe.log_error(
            message=f"Error checking table structure: {str(e)}",
            title="CrossChex Debug - Table Structure Error"
        )
        return None

@frappe.whitelist(allow_guest=True)
def make_attendace(**kwargs):
    try:
        data = None
        if kwargs.get("records"):
            data = kwargs.get("records")
        if not data:
            raise Exception("Payload not found " + str(kwargs))
        
        # Create log entry
        crosschex_log = frappe.new_doc("CrossChex Log")
        crosschex_log.log_type = "Webhook"
        crosschex_log.status = "Processing"
        crosschex_log.request_payload = json.dumps(data)
        crosschex_log.request_method = "POST"
        crosschex_log.webhook_source = "CrossChex Cloud"
        crosschex_log.save(ignore_permissions=True)
        
        # Process attendance records
        processed_count, created_count, error_count = create_attendance_log(data)
        
        # Update log with results
        crosschex_log.records_processed = processed_count
        crosschex_log.checkins_created = created_count
        crosschex_log.status = "Success" if error_count == 0 else ("Partial Success" if created_count > 0 else "Failed")
        crosschex_log.processing_status = "Completed"
        if error_count > 0:
            crosschex_log.error_message = f"{error_count} records failed to process"
        crosschex_log.save(ignore_permissions=True)
        
        frappe.local.response["code"] = 200
        frappe.local.response["msg"] = f"Processed {processed_count} records, created {created_count} check-ins"
        
    except Exception as e:
        frappe.log_error(message=str(e), title="CrossChex Webhook")
        frappe.local.response["status_code"] = 200  # Return 200 to prevent webhook retries
        frappe.local.response["message"] = f"Processed with warnings: {str(e)}"

def create_attendance_log(args):
    if type(args) == str:
        args = json.loads(args)

    processed_count = 0
    created_count = 0
    error_count = 0

    for i in args:
        processed_count += 1
        attn_id = None
        try:
            if i.get("employee"):
                attn_id = i.get("employee").get("workno")
            if not attn_id:
                error_count += 1
                frappe.log_error(
                    message=f"No workno found in payload: {json.dumps(i)}", 
                    title="CrossChex Webhook - Missing workno"
                )
                continue
            
            # Convert attn_id to int for comparison with attendance_device_id (Int field)
            try:
                attn_id_int = int(attn_id)
            except (ValueError, TypeError):
                error_count += 1
                frappe.log_error(
                    message=f"Invalid workno format '{attn_id}': {json.dumps(i)}", 
                    title="CrossChex Webhook - Invalid workno"
                )
                continue
            
            # Look up employee by attendance_device_id
            employee = frappe.db.get_value("Employee", {"attendance_device_id": attn_id_int, "status": "Active"}, "name")
            if not employee:
                error_count += 1
                frappe.log_error(
                    message=f"Employee not found for attendance_device_id {attn_id_int}. Data: {json.dumps(i)}", 
                    title="CrossChex Webhook - Employee not found"
                )
                continue
            
            # Get employee details and attendance_device_id for logging and shift lookup
            employee_details = frappe.db.get_value("Employee", employee, ["employee_name", "department", "designation", "attendance_device_id"], as_dict=True)
            
            log_type = logMap.get(i.get("checktype", i.get("check_type", 0)), "IN")  # Handle both field names
            device_id = i.get("device", {}).get("name", "") if i.get("device") else ""
            
            # Parse checktime from ISO format and remove timezone for MySQL compatibility
            checktime_str = i.get("checktime")
            if checktime_str:
                try:
                    # Simple regex approach to remove timezone info
                    import re
                    # Remove timezone info: +00:00, -05:00, Z, etc.
                    datetime_clean = re.sub(r'[+-]\d{2}:\d{2}$|Z$', '', checktime_str)
                    
                    # Parse the cleaned datetime string - this gives us the device's actual timestamp
                    checkin_time = datetime.strptime(datetime_clean, '%Y-%m-%dT%H:%M:%S')
                    
                    frappe.logger().info(
                        f"CrossChex Webhook: Parsed device time '{checktime_str}' to '{checkin_time}' for employee {attn_id_int}"
                    )
                        
                except Exception as parse_error:
                    # Fallback to current time if parsing fails
                    checkin_time = datetime.now()
                    frappe.log_error(
                        message=f"Error parsing checktime '{checktime_str}': {str(parse_error)}", 
                        title="CrossChex Webhook - Time Parse Error"
                    )
            else:
                checkin_time = datetime.now()
                frappe.log_error(
                    message=f"No checktime provided in payload: {json.dumps(i)}", 
                    title="CrossChex Webhook - Missing checktime"
                )
            
            # Try to get shift from payload first, then from shift assignment
            shift = None
            if i.get("device") and i.get("device").get("shift"):
                # Shift provided in payload
                shift = i.get("device").get("shift")
            else:
                # Try to find shift from Shift Assignment using employee field
                try:
                    if employee:
                        shift_assignment = frappe.db.get_value(
                            "Shift Assignment",
                            {
                                "employee": employee,
                                "docstatus": 1,
                                "start_date": ("<=", checkin_time.date())
                            },
                            ["shift_type"],
                            order_by="start_date desc"
                        )
                        if shift_assignment:
                            shift = shift_assignment
                except Exception as shift_error:
                    frappe.log_error(
                        message=f"Error finding shift assignment for employee {employee}: {str(shift_error)}",
                        title="CrossChex Webhook - Shift Lookup Error"
                    )
            
            # Create a simple timestamp-based name
            import time
            timestamp = str(int(time.time() * 1000))
            checkin_name = f"CKIN-{timestamp}"
            
            # Check for duplicate using CrossChex UUID to prevent re-importing same record
            crosschex_uuid = i.get("uuid")
            if crosschex_uuid:
                # Check if a checkin with this UUID already exists
                existing_checkin = frappe.db.exists(
                    "Employee Checkin",
                    {"custom_crosschex_uuid": crosschex_uuid}
                )
                
                if existing_checkin:
                    # Log as info, not error - this is expected behavior
                    frappe.logger().info(
                        f"CrossChex Webhook: Skipping duplicate record with UUID {crosschex_uuid}. Employee: {employee}, Time: {checkin_time}"
                    )
                    continue  # Skip this record, it's already imported
            
            try:
                # Use Frappe document creation instead of direct SQL to avoid table structure issues
                checkin_doc = frappe.new_doc("Employee Checkin")
                checkin_doc.employee = employee
                checkin_doc.log_type = log_type
                checkin_doc.device_id = device_id
                
                # CRITICAL FIX: Set the time field with the actual device timestamp (datetime object)
                # Do NOT convert to string - Frappe expects datetime objects for Datetime fields
                checkin_doc.time = checkin_time
                checkin_doc.naming_series = 'CKIN/.YY./.MM./.#####'
                
                # Always skip ERPNext auto attendance (handled by our custom workflow)
                checkin_doc.skip_auto_attendance = 1
                
                # Set CrossChex UUID if available
                if i.get("uuid"):
                    checkin_doc.custom_crosschex_uuid = i.get("uuid")
                
                # Set shift if available
                if shift:
                    checkin_doc.shift = shift
                
                # Employee name, department, and designation will be fetched automatically via fetch_from
                # But we can set them explicitly to ensure they're populated
                if employee_details:
                    checkin_doc.employee_name = employee_details.get("employee_name", "")
                    checkin_doc.department = employee_details.get("department", "")
                    checkin_doc.designation = employee_details.get("designation", "")
                
                # Save the document (this will handle all validations and field mappings)
                # Re-enable validation to test our fixes
                checkin_doc.insert(ignore_permissions=True)
                frappe.db.commit()
                created_count += 1
                
                # Log success as info, not error
                frappe.logger().info(
                    f"CrossChex Webhook: Successfully created checkin {checkin_doc.name} for employee {employee} with UUID {i.get('uuid', 'N/A')}"
                )
                
            except Exception as insert_error:
                error_count += 1
                frappe.log_error(
                    message=f"Error inserting checkin for employee {employee}: {str(insert_error)}\nData: {json.dumps(i)}", 
                    title="CrossChex Webhook - Insert Error"
                )
                
        except Exception as e:
            error_count += 1
            frappe.log_error(
                message=f"Error processing attendance for employee {attn_id if 'attn_id' in locals() else 'unknown'}: {str(e)}\nData: {json.dumps(i)}", 
                title="CrossChex Webhook - Processing Error"
            )

    return processed_count, created_count, error_count