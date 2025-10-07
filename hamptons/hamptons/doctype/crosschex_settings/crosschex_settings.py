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
            if not self.api_key:
                frappe.throw("API Key is required when sync is enabled")
            if not self.api_secret:
                frappe.throw("API Secret is required when sync is enabled")
            if not self.api_url:
                frappe.throw("API URL is required when sync is enabled")
        
        # Ensure API URL ends with /
        if self.api_url and not self.api_url.endswith('/'):
            self.api_url += '/'
    
    def on_update(self):
        """Called after the document is saved"""
        # Clear token if API credentials changed
        if self.has_value_changed("api_key") or self.has_value_changed("api_secret"):
            self.db_set('token', None, update_modified=False)
            self.db_set('token_expires', None, update_modified=False)
            self.db_set('connection_status', 'Not Tested', update_modified=False)
    
    @frappe.whitelist()
    def test_connection(self):
        """Test the API connection and generate token"""
        try:
            if not self.api_key or not self.api_secret:
                return {"success": False, "error": "API Key and Secret are required"}
            
            # Generate token
            token_result = self.generate_token()
            
            if token_result.get("success"):
                # Update connection status
                self.db_set('connection_status', 'Connected', update_modified=False)
                self.db_set('last_token_generated', now_datetime(), update_modified=False)
                frappe.db.commit()
                
                return {
                    "success": True,
                    "message": "Connection successful! Token generated and saved."
                }
            else:
                self.db_set('connection_status', 'Error', update_modified=False)
                frappe.db.commit()
                
                return {
                    "success": False,
                    "error": f"Connection failed: {token_result.get('error')}"
                }
                
        except Exception as e:
            self.db_set('connection_status', 'Error', update_modified=False)
            frappe.db.commit()
            
            return {"success": False, "error": f"Connection test failed: {str(e)}"}
    
    @frappe.whitelist()
    def sync_now(self):
        """Manually trigger sync"""
        try:
            if not self.enable_realtime_sync:
                return {"success": False, "error": "CrossChex sync is not enabled"}
            
            # Import here to avoid circular imports
            from hamptons.crosschex_cloud.api.sync import manual_sync_crosschex_cloud
            
            result = manual_sync_crosschex_cloud()
            
            # Update sync status
            if result.get("success"):
                self.db_set('last_sync_time', now_datetime(), update_modified=False)
                self.db_set('last_sync_status', result.get('message', 'Success'), update_modified=False)
            else:
                self.db_set('last_sync_status', f"Error: {result.get('error')}", update_modified=False)
            
            frappe.db.commit()
            return result
            
        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            self.db_set('last_sync_status', error_msg, update_modified=False)
            frappe.db.commit()
            
            return {"success": False, "error": error_msg}
    
    @frappe.whitelist()
    def reset_token(self):
        """Reset/clear the current token"""
        try:
            self.db_set('token', None, update_modified=False)
            self.db_set('token_expires', None, update_modified=False)
            self.db_set('connection_status', 'Not Tested', update_modified=False)
            frappe.db.commit()
            
            return {"success": True, "message": "Token has been reset"}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to reset token: {str(e)}"}
    
    @frappe.whitelist()
    def clear_logs(self):
        """Clear CrossChex logs"""
        try:
            # Delete old CrossChex logs
            cutoff_date = get_datetime() - timedelta(days=int(self.log_retention_days or 30))
            
            frappe.db.sql("""
                DELETE FROM `tabCrossChex Log`
                WHERE creation < %s
            """, (cutoff_date,))
            
            frappe.db.commit()
            
            return {"success": True, "message": f"Logs older than {self.log_retention_days or 30} days have been cleared"}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to clear logs: {str(e)}"}
    
    def generate_token(self):
        """Generate CrossChex Cloud access token"""
        try:
            import uuid
            
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
                    "api_key": self.api_key,
                    "api_secret": self.get_password('api_secret')
                }
            }
            
            response = requests.post(
                self.api_url or "https://api.us.crosschexcloud.com/",
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
                    # Save token
                    self.db_set('token', data['payload']['token'], update_modified=False)
                    
                    if 'expires' in data['payload']:
                        expires_str = data['payload']['expires']
                        try:
                            expires_dt = datetime.strptime(expires_str, "%Y-%m-%dT%H:%M:%S+00:00")
                            self.db_set('token_expires', expires_dt, update_modified=False)
                        except:
                            pass
                    
                    frappe.db.commit()
                    
                    return {
                        "success": True,
                        "token": data['payload']['token'],
                        "expires": data['payload'].get('expires')
                    }
            
            return {"success": False, "error": f"API returned status {response.status_code}: {response.text}"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_valid_token(self):
        """Get a valid access token, generating one if needed"""
        try:
            current_token = self.get_password('token')
            
            # Check if token exists and is not expired
            if current_token and self.token_expires:
                if get_datetime(self.token_expires) > now_datetime():
                    return current_token
            
            # Generate new token
            token_result = self.generate_token()
            if token_result.get("success"):
                return token_result.get("token")
            
            return None
            
        except Exception as e:
            frappe.logger().error(f"Error getting valid token: {str(e)}")
            return None

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
        
        return {
            "sync_enabled": settings.enable_realtime_sync,
            "last_sync": settings.last_sync_time,
            "last_status": settings.last_sync_status,
            "connection_status": settings.connection_status,
            "api_configured": bool(settings.api_key and settings.api_secret),
            "has_token": bool(settings.get_password('token'))
        }
        
    except Exception as e:
        return {"error": f"Error getting status: {str(e)}"}

def scheduled_attendance_sync():
    """Scheduled function for attendance sync"""
    try:
        if not frappe.db.exists("DocType", "Crosschex Settings"):
            return
        
        settings = frappe.get_single("Crosschex Settings")
        if not settings.enable_realtime_sync:
            return
        
        # Import here to avoid circular imports
        from hamptons.crosschex_cloud.api.sync import manual_sync_crosschex_cloud
        
        result = manual_sync_crosschex_cloud()
        
        if result.get("success"):
            settings.db_set('last_sync_time', now_datetime(), update_modified=False)
            settings.db_set('last_sync_status', f"Auto-sync: {result.get('message')}", update_modified=False)
        else:
            settings.db_set('last_sync_status', f"Auto-sync failed: {result.get('error')}", update_modified=False)
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.logger().error(f"Error in scheduled_attendance_sync: {str(e)}")

def check_and_refresh_token():
    """Scheduled function to check and refresh token if needed"""
    try:
        if not frappe.db.exists("DocType", "Crosschex Settings"):
            return
        
        settings = frappe.get_single("Crosschex Settings")
        if not settings.enable_realtime_sync:
            return
        
        # Check if token needs refresh
        current_token = settings.get_password('token')
        if not current_token or (settings.token_expires and get_datetime(settings.token_expires) <= now_datetime()):
            settings.generate_token()
            
    except Exception as e:
        frappe.logger().error(f"Error in check_and_refresh_token: {str(e)}")

def auto_generate_token():
    """Scheduled function to auto-generate token for CrossChex Cloud API"""
    try:
        if not frappe.db.exists("DocType", "Crosschex Settings"):
            return
        
        settings = frappe.get_single("Crosschex Settings")
        if not settings.enable_realtime_sync:
            return
        
        # Check if we have valid credentials
        if not (settings.crosschex_username and settings.get_password('crosschex_password')):
            frappe.logger().info("CrossChex credentials not configured, skipping auto token generation")
            return
        
        # Check if token needs refresh (expires within next 30 minutes)
        current_token = settings.get_password('token')
        token_expired = False
        
        if not current_token:
            token_expired = True
        elif settings.token_expires:
            # Check if token expires within the next 30 minutes
            expiry_time = get_datetime(settings.token_expires)
            current_time = now_datetime()
            time_until_expiry = expiry_time - current_time
            
            if time_until_expiry.total_seconds() <= 1800:  # 30 minutes
                token_expired = True
        
        if token_expired:
            frappe.logger().info("Auto-generating new CrossChex token")
            settings.generate_token()
            
            # Create log entry for auto token generation
            if frappe.db.exists("DocType", "Crosschex Log"):
                log = frappe.get_doc({
                    "doctype": "Crosschex Log",
                    "endpoint": "/api/token",
                    "method": "POST",
                    "status": "Success",
                    "sync_type": "Auto Token Generation",
                    "message": "Token automatically generated by scheduler",
                    "processing_time": 0
                })
                log.insert(ignore_permissions=True)
                frappe.db.commit()
            
    except Exception as e:
        frappe.logger().error(f"Error in auto_generate_token: {str(e)}")
        
        # Create error log entry
        if frappe.db.exists("DocType", "Crosschex Log"):
            try:
                error_log = frappe.get_doc({
                    "doctype": "Crosschex Log",
                    "endpoint": "/api/token",
                    "method": "POST",
                    "status": "Error",
                    "sync_type": "Auto Token Generation",
                    "message": f"Error in auto token generation: {str(e)}",
                    "error_details": str(e),
                    "processing_time": 0
                })
                error_log.insert(ignore_permissions=True)
                frappe.db.commit()
            except:
                pass  # Don't fail if logging fails
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
        
        # Step 2: Fetch attendance data
        end_time = datetime.utcnow()
        begin_time = end_time - timedelta(hours=24)
        
        begin_time_str = begin_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        
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
                "page": 1,
                "per_page": 1000
            }
        }
        
        response = requests.post(
            api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code != 200:
            return {"success": False, "error": f"Failed to fetch attendance data: {response.status_code}"}
        
        data = response.json()
        
        if 'payload' not in data or 'list' not in data['payload']:
            return {"success": False, "error": "No attendance data in response"}
        
        records = data['payload']['list']
        
        # Step 3: Process attendance records
        processed_count = 0
        errors = []
        
        for record in records:
            try:
                create_attendance_log([record])
                processed_count += 1
            except Exception as e:
                errors.append(f"Error processing record: {str(e)}")
                continue
        
        return {
            "success": True,
            "processed": processed_count,
            "errors": len(errors),
            "message": f"Successfully synced {processed_count} attendance records from {config_name or api_url}"
        }
        
    except Exception as e:
        frappe.log_error(f"Individual device sync failed: {str(e)}", "CrossChex Sync Error")
        return {"success": False, "error": str(e)}