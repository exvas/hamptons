# Copyright (c) 2025, Hamptons and contributors
# For license information, please see license.txt

# Copyright (c) 2025, sammish and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime
import requests
import json
from datetime import datetime, timedelta

class CrosschexSettings(Document):
    def validate(self):
        """Validate CrossChex Settings before saving"""
        if self.enable_realtime_sync:
            # Check if multi-device config is set
            has_multi_device_config = self.api_configurations and len(self.api_configurations) > 0

            if not has_multi_device_config:
                frappe.throw("Please configure at least one API Configuration when realtime sync is enabled")

            # Validate each API configuration entry
            for idx, config in enumerate(self.api_configurations, start=1):
                if not config.api_url:
                    frappe.throw(f"API URL is required for configuration row {idx}")
                if not config.api_key:
                    frappe.throw(f"API Key is required for configuration row {idx}")
                if not config.get_password('api_secret'):
                    frappe.throw(f"API Secret is required for configuration row {idx}")

        # Ensure API URL ends with / for all configurations
        if self.api_configurations:
            for config in self.api_configurations:
                if config.api_url and not config.api_url.endswith('/'):
                    config.api_url += '/'

@frappe.whitelist()
def test_individual_api_config(api_url, api_key, config_row_name, config_name=None):
    """Test an individual API configuration"""
    try:
        import uuid
        
        # Retrieve the actual password from the child table row using get_doc and get_password
        try:
            config_doc = frappe.get_doc("CrossChex API Configuration", config_row_name)
            api_secret = config_doc.get_password('api_secret')
        except Exception as e:
            return {"success": False, "error": f"Failed to retrieve API Secret: {str(e)}"}
        
        if not api_secret:
            return {"success": False, "error": "API Secret not found. Please enter the API Secret and save the document first."}
        
        request_id = str(uuid.uuid4())
        
        # Ensure API URL ends with /
        if not api_url.endswith('/'):
            api_url += '/'
        
        payload = {
            "header": {
                "nameSpace": "authorize.token",
                "nameAction": "token",
                "version": "1.0",
                "requestId": request_id,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
            },
            "payload": {
                "api_key": api_key,
                "api_secret": api_secret
            }
        }
        
        response = requests.post(
            api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for error response
            if 'header' in data and data['header'].get('nameSpace') == 'System':
                error_type = data.get('payload', {}).get('type', 'Unknown')
                error_message = data.get('payload', {}).get('message', 'Unknown error')
                
                if error_type == 'AUTH_ERROR':
                    return {"success": False, "error": "Authentication failed. Please verify your API Key and API Secret."}
                else:
                    return {"success": False, "error": f"{error_type}: {error_message}"}
            
            # Success response
            elif 'payload' in data and 'token' in data['payload']:
                expires_raw = data['payload'].get('expires')
                expires_formatted = None
                
                # Convert ISO 8601 datetime with timezone to MySQL-compatible format
                if expires_raw:
                    try:
                        from dateutil import parser
                        dt = parser.parse(expires_raw)
                        # Convert to MySQL datetime format (YYYY-MM-DD HH:MM:SS)
                        expires_formatted = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        expires_formatted = None
                
                return {
                    "success": True,
                    "token": data['payload']['token'],
                    "expires": expires_formatted,
                    "message": f"Connection to {config_name or api_url} successful!"
                }
        
        return {"success": False, "error": f"API returned status {response.status_code}: {response.text}"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_crosschex_status():
    """Get current CrossChex sync status"""
    try:
        if not frappe.db.exists("DocType", "Crosschex Settings"):
            return {"error": "Crosschex Settings doctype not found"}

        settings = frappe.get_single("Crosschex Settings")

        # Check if at least one API configuration exists
        api_configured = settings.api_configurations and len(settings.api_configurations) > 0

        # Check if at least one device has a valid token
        has_token = False
        if api_configured:
            for config in settings.api_configurations:
                if config.get_password('token'):
                    has_token = True
                    break

        return {
            "sync_enabled": settings.enable_realtime_sync,
            "last_sync": settings.last_sync_time,
            "last_status": settings.last_sync_status,
            "connection_status": settings.connection_status,
            "api_configured": api_configured,
            "has_token": has_token,
            "device_count": len(settings.api_configurations) if api_configured else 0
        }

    except Exception as e:
        return {"error": f"Error getting status: {str(e)}"}

def scheduled_attendance_sync():
    """Scheduled function for attendance sync - syncs all configured devices"""
    try:
        if not frappe.db.exists("DocType", "Crosschex Settings"):
            return
        
        settings = frappe.get_single("Crosschex Settings")
        if not settings.enable_realtime_sync:
            return
        
        # Check if we have API configurations (multi-device setup)
        if not settings.api_configurations or len(settings.api_configurations) == 0:
            frappe.logger().info("CrossChex sync skipped: No API configurations found")
            return

        # Sync all configured devices from the child table
        total_processed = 0
        total_errors = 0
        sync_results = []

        for config in settings.api_configurations:
            try:
                result = sync_individual_device(
                    api_url=config.api_url,
                    api_key=config.api_key,
                    config_row_name=config.name,
                    config_name=config.configuration_name
                )

                if result.get("success"):
                    total_processed += result.get("processed", 0)
                    sync_results.append(f"{config.configuration_name}: {result.get('processed', 0)} records")
                else:
                    total_errors += 1
                    sync_results.append(f"{config.configuration_name}: Error - {result.get('error', 'Unknown')}")

            except Exception as e:
                total_errors += 1
                sync_results.append(f"{config.configuration_name}: Exception - {str(e)}")
                frappe.logger().error(f"Error syncing device {config.configuration_name}: {str(e)}")

        # Update settings with sync summary
        status_message = f"Auto-sync: Processed {total_processed} records from {len(settings.api_configurations)} devices. " + "; ".join(sync_results)
        settings.db_set('last_sync_time', now_datetime(), update_modified=False)
        settings.db_set('last_sync_status', status_message[:255], update_modified=False)  # Limit to 255 chars
        frappe.db.commit()
        
    except Exception as e:
        frappe.logger().error(f"Error in scheduled_attendance_sync: {str(e)}")

def check_and_refresh_token():
    """Scheduled function to check and refresh tokens for all devices"""
    try:
        if not frappe.db.exists("DocType", "Crosschex Settings"):
            return
        
        settings = frappe.get_single("Crosschex Settings")
        if not settings.enable_realtime_sync:
            return
        
        # Refresh tokens for all API configurations
        if not settings.api_configurations or len(settings.api_configurations) == 0:
            frappe.logger().info("CrossChex token refresh skipped: No API configurations found")
            return

        for config in settings.api_configurations:
            try:
                # Check if token needs refresh
                token = config.get_password('token') if hasattr(config, 'token') else None
                token_expires = config.token_expires if hasattr(config, 'token_expires') else None

                needs_refresh = False
                if not token:
                    needs_refresh = True
                elif token_expires:
                    try:
                        expires_dt = get_datetime(token_expires)
                        # Refresh if expires within next 30 minutes
                        if (expires_dt - now_datetime()).total_seconds() <= 1800:
                            needs_refresh = True
                    except:
                        needs_refresh = True

                if needs_refresh:
                    # Generate new token via test connection
                    test_individual_api_config(
                        api_url=config.api_url,
                        api_key=config.api_key,
                        config_row_name=config.name,
                        config_name=config.configuration_name
                    )
                    frappe.logger().info(f"Token refreshed for {config.configuration_name}")

            except Exception as e:
                frappe.logger().error(f"Error refreshing token for {config.configuration_name}: {str(e)}")
            
    except Exception as e:
        frappe.logger().error(f"Error in check_and_refresh_token: {str(e)}")
@frappe.whitelist()
def sync_individual_device(api_url, api_key, config_row_name, config_name=None):
    """Sync attendance data from a specific CrossChex device configuration"""
    try:
        import uuid
        from hamptons.crosschex_cloud.api.attendance import create_attendance_log
        
        # Retrieve the actual password from the child table row
        try:
            config_doc = frappe.get_doc("CrossChex API Configuration", config_row_name)
            api_secret = config_doc.get_password('api_secret')
        except Exception as e:
            return {"success": False, "error": f"Failed to retrieve API Secret: {str(e)}"}
        
        if not api_secret:
            return {"success": False, "error": "API Secret not found. Please enter the API Secret and save the document first."}
        
        # Ensure API URL ends with /
        if not api_url.endswith('/'):
            api_url += '/'
        
        # Step 1: Generate or retrieve token
        token = config_doc.get_password('token')
        token_expires = config_doc.token_expires
        
        # Check if token is valid
        needs_new_token = True
        if token and token_expires:
            try:
                expires_dt = get_datetime(token_expires)
                if expires_dt > now_datetime():
                    needs_new_token = False
            except:
                pass
        
        # Generate new token if needed
        if needs_new_token:
            request_id = str(uuid.uuid4())
            
            payload = {
                "header": {
                    "nameSpace": "authorize.token",
                    "nameAction": "token",
                    "version": "1.0",
                    "requestId": request_id,
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
                },
                "payload": {
                    "api_key": api_key,
                    "api_secret": api_secret
                }
            }
            
            response = requests.post(
                api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for error response
                if 'header' in data and data['header'].get('nameSpace') == 'System':
                    error_type = data.get('payload', {}).get('type', 'Unknown')
                    error_message = data.get('payload', {}).get('message', 'Unknown error')
                    return {"success": False, "error": f"Authentication failed: {error_type} - {error_message}"}
                
                # Success response
                elif 'payload' in data and 'token' in data['payload']:
                    token = data['payload']['token']
                    expires_raw = data['payload'].get('expires')
                    
                    # Save token to database
                    config_doc.db_set('token', token, update_modified=False)
                    
                    if expires_raw:
                        try:
                            from dateutil import parser
                            dt = parser.parse(expires_raw)
                            expires_formatted = dt.strftime('%Y-%m-%d %H:%M:%S')
                            config_doc.db_set('token_expires', expires_formatted, update_modified=False)
                        except:
                            pass
                    
                    config_doc.db_set('last_token_generated', now_datetime(), update_modified=False)
                    frappe.db.commit()
                else:
                    return {"success": False, "error": "Failed to generate token"}
            else:
                return {"success": False, "error": f"API returned status {response.status_code}"}
        
        # Step 2: Fetch attendance data with pagination support
        end_time = datetime.utcnow()

        # Smart sync strategy to ensure no records are missed:
        # - Always fetch from start of current day (midnight) to capture all today's records
        # - UUID duplicate detection prevents re-processing existing records
        # - This ensures devices that were offline or had delayed check-ins don't lose data
        last_sync = config_doc.last_sync_time

        # Calculate start of today in UTC (midnight)
        current_datetime = now_datetime()
        today_start_utc = datetime.combine(current_datetime.date(), datetime.min.time())

        if last_sync:
            try:
                last_sync_dt = get_datetime(last_sync)
                # If last sync was today, fetch from start of today
                # This ensures we capture any records created earlier today that were missed
                if last_sync_dt.date() == today_start_utc.date():
                    begin_time = today_start_utc
                else:
                    # Last sync was yesterday or earlier - fetch from that date's start
                    begin_time = datetime.combine(last_sync_dt.date(), datetime.min.time())
            except:
                # Fallback: fetch last 7 days
                begin_time = end_time - timedelta(days=7)
        else:
            # Initial sync: get last 30 days of data
            begin_time = end_time - timedelta(days=30)

        begin_time_str = begin_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        # Fetch all pages of data
        all_records = []
        page = 1
        per_page = 1000
        total_pages = 1  # Will be updated from API response

        while page <= total_pages:
            request_id = str(uuid.uuid4())

            payload = {
                "header": {
                    "nameSpace": "attendance.record",
                    "nameAction": "getrecord",
                    "version": "1.0",
                    "requestId": request_id,
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
                },
                "authorize": {
                    "type": "token",
                    "token": token
                },
                "payload": {
                    "begin_time": begin_time_str,
                    "end_time": end_time_str,
                    "order": "asc",
                    "page": page,
                    "per_page": per_page
                }
            }

            response = requests.post(
                api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            if response.status_code != 200:
                if page == 1:
                    return {"success": False, "error": f"Failed to fetch attendance data: {response.status_code}"}
                else:
                    # If we already got some pages, break and process what we have
                    frappe.logger().warning(f"Failed to fetch page {page}, stopping pagination. Got {len(all_records)} records so far.")
                    break

            data = response.json()

            if 'payload' not in data or 'list' not in data['payload']:
                if page == 1:
                    return {"success": False, "error": "No attendance data in response"}
                else:
                    break

            page_records = data['payload']['list']
            all_records.extend(page_records)

            # Check if there are more pages
            # CrossChex API returns total count in payload
            if 'total' in data['payload']:
                total_records = data['payload']['total']
                total_pages = (total_records + per_page - 1) // per_page  # Calculate total pages
                frappe.logger().info(
                    f"CrossChex Sync Page {page}/{total_pages}: Fetched {len(page_records)} records "
                    f"(Total so far: {len(all_records)}/{total_records})"
                )
            else:
                # If no total field, check if we got a full page
                if len(page_records) < per_page:
                    # Last page
                    break

            page += 1

            # Safety limit: don't fetch more than 10 pages (10,000 records) in one sync
            if page > 10:
                frappe.logger().warning(f"Reached page limit (10), stopping. Fetched {len(all_records)} records.")
                break

        records = all_records

        # Log sync summary
        if records:
            frappe.logger().info(
                f"CrossChex Sync Complete: Fetched {len(records)} total records from {config_name or api_url} "
                f"(first: {records[0].get('checktime', 'N/A')}, last: {records[-1].get('checktime', 'N/A')})"
            )
        
        # Step 3: Process attendance records
        processed_count = 0
        errors = []
        
        for record in records:
            try:
                # Transform API response format to webhook format expected by create_attendance_log
                # API format: {"emp_pin": "1040", "checktime": "...", "check_type": 0, ...}
                # Webhook format: {"employee": {"workno": "1040"}, "checktime": "...", "checktype": 0, ...}
                
                # Try to extract employee identifier from multiple possible field names
                employee_id = (
                    record.get("emp_pin") or 
                    record.get("employee_id") or 
                    record.get("empno") or
                    record.get("emp_code") or
                    record.get("pin") or
                    record.get("workno") or
                    (record.get("employee", {}).get("workno") if isinstance(record.get("employee"), dict) else None) or
                    (record.get("employee", {}).get("pin") if isinstance(record.get("employee"), dict) else None) or
                    (record.get("employee", {}).get("emp_pin") if isinstance(record.get("employee"), dict) else None)
                )
                
                # Log the record if employee_id is missing to help debug
                if not employee_id:
                    frappe.log_error(
                        message=f"Cannot find employee identifier in record. All fields: {json.dumps(record, indent=2)}",
                        title="CrossChex Sync - Missing Employee ID"
                    )
                    errors.append("Missing employee identifier in record")
                    continue
                
                transformed_record = {
                    "employee": {
                        "workno": employee_id
                    },
                    "checktime": record.get("checktime") or record.get("check_time") or record.get("time"),
                    "checktype": record.get("check_type") if "check_type" in record else record.get("checktype", 0),
                    "uuid": record.get("uuid") or record.get("id") or record.get("record_id"),
                    "device": record.get("device", {})
                }
                
                create_attendance_log([transformed_record])
                processed_count += 1
            except Exception as e:
                errors.append(f"Error processing record: {str(e)}")
                frappe.log_error(
                    message=f"Failed to process record: {json.dumps(record, indent=2)}\nError: {str(e)}",
                    title="CrossChex Sync - Record Processing Error"
                )
                continue
        
        # Update last sync time on the config row
        config_doc.db_set('last_sync_time', now_datetime(), update_modified=False)
        frappe.db.commit()
        
        return {
            "success": True,
            "processed": processed_count,
            "errors": len(errors),
            "message": f"Successfully synced {processed_count} attendance records from {config_name or api_url}"
        }
        
    except Exception as e:
        frappe.log_error(f"Individual device sync failed: {str(e)}", "CrossChex Sync Error")
        return {"success": False, "error": str(e)}