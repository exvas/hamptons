# Copyright (c) 2025, sammish and contributors
# For license information, please see license.txt

import frappe
import requests
import json
from datetime import datetime, timedelta
from hamptons.crosschex_cloud.api.attendance import create_attendance_log

@frappe.whitelist()
def manual_sync_crosschex_cloud():
    """
    Manually sync attendance data from CrossChex Cloud API using Crosschex Settings
    """
    try:
        # Get CrossChex settings
        settings = get_crosschex_settings()
        if not settings:
            return {"success": False, "error": "Crosschex Settings not configured"}
        
        if not settings.get("api_key") or not settings.get("api_secret"):
            return {"success": False, "error": "API Key and Secret not configured"}
        
        # Generate token if needed
        access_token = settings.get("access_token")
        if not access_token:
            frappe.logger().info("Generating new access token...")
            token_result = generate_crosschex_token(settings.get("api_key"), settings.get("api_secret"))
            
            if not token_result.get("success"):
                return {"success": False, "error": f"Failed to generate token: {token_result.get('error')}"}
            
            access_token = token_result.get("token")
            
            # Save token to settings
            crosschex_doc = frappe.get_single("Crosschex Settings")
            crosschex_doc.db_set('token', access_token, update_modified=False)
            frappe.db.commit()
        
        # Fetch attendance data
        attendance_data = fetch_attendance_from_crosschex_api(settings, access_token)
        
        if not attendance_data:
            return {"success": True, "processed": 0, "message": "No new attendance data found"}
        
        # Process the fetched data using existing attendance logic
        processed_count = 0
        errors = []
        
        for record in attendance_data:
            try:
                # Use existing attendance processing
                create_attendance_log([record])
                processed_count += 1
                
            except Exception as e:
                errors.append(f"Error processing record: {str(e)}")
                continue
        
        # Update last sync time
        crosschex_doc = frappe.get_single("Crosschex Settings")
        crosschex_doc.db_set('last_sync_time', frappe.utils.now_datetime(), update_modified=False)
        crosschex_doc.db_set('last_sync_status', f"Success - {processed_count} records processed", update_modified=False)
        frappe.db.commit()
        
        return {
            "success": True,
            "processed": processed_count,
            "errors": len(errors),
            "message": f"Successfully processed {processed_count} attendance records"
        }
        
    except Exception as e:
        frappe.logger().error(f"CrossChex Cloud sync failed: {str(e)}")
        
        # Update error status
        try:
            crosschex_doc = frappe.get_single("Crosschex Settings")
            crosschex_doc.db_set('last_sync_status', f"Error: {str(e)}", update_modified=False)
            frappe.db.commit()
        except:
            pass
        
        return {"success": False, "error": f"Sync failed: {str(e)}"}

def get_crosschex_settings():
    """
    Get CrossChex settings from the Crosschex Settings doctype
    """
    try:
        if not frappe.db.exists("DocType", "Crosschex Settings"):
            return None
        
        settings = frappe.get_single("Crosschex Settings")
        if not settings:
            return None
        
        return {
            "api_url": settings.api_url or "https://api.us.crosschexcloud.com/",
            "api_key": getattr(settings, "api_key", None),
            "api_secret": settings.get_password('api_secret') if hasattr(settings, 'api_secret') else None,
            "access_token": getattr(settings, 'token', None),
            "enabled": getattr(settings, "enable_realtime_sync", True),
            "last_sync": getattr(settings, "last_sync_time", None)
        }
    except Exception as e:
        frappe.logger().error(f"Error getting Crosschex settings: {str(e)}")
        return None

def generate_crosschex_token(api_key, api_secret):
    """
    Generate CrossChex Cloud access token
    """
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
                "api_key": api_key,
                "api_secret": api_secret
            }
        }
        
        response = requests.post(
            "https://api.us.crosschexcloud.com/",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'payload' in data and 'token' in data['payload']:
                return {
                    "success": True,
                    "token": data['payload']['token'],
                    "expires": data['payload']['expires']
                }
        
        return {"success": False, "error": f"API returned status {response.status_code}"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def fetch_attendance_from_crosschex_api(settings, access_token):
    """
    Fetch attendance records from CrossChex Cloud API
    """
    try:
        import uuid
        
        # Get date range for sync (last 365 days to capture historical records)
        end_time = datetime.utcnow()
        begin_time = end_time - timedelta(days=365)
        
        # Format dates for API
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
                "token": access_token
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
            settings.get("api_url"),
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'payload' in data and 'list' in data['payload']:
                records = data['payload']['list']
                frappe.logger().info(f"Fetched {len(records)} attendance records from CrossChex Cloud")
                
                # Log sample record for debugging
                if records:
                    frappe.log_error(
                        message=f"CrossChex API Response Sample:\n" +
                                f"Total records: {len(records)}\n" +
                                f"Sample record: {json.dumps(records[0], indent=2)}",
                        title="CrossChex Sync - API Response"
                    )
                
                # Transform API response format to webhook format
                # API format: {"emp_pin": "1040", "checktime": "...", "check_type": 0, ...}
                # Webhook format: {"employee": {"workno": "1040"}, "checktime": "...", "checktype": 0, ...}
                transformed_records = []
                for record in records:
                    transformed_record = {
                        "employee": {
                            "workno": record.get("emp_pin") or record.get("employee_id") or record.get("workno")
                        },
                        "checktime": record.get("checktime") or record.get("check_time"),
                        "checktype": record.get("check_type") if "check_type" in record else record.get("checktype", 0),
                        "uuid": record.get("uuid") or record.get("id"),
                        "device": record.get("device", {})
                    }
                    transformed_records.append(transformed_record)
                
                return transformed_records
        
        frappe.logger().error(f"CrossChex API request failed: {response.status_code}")
        return []
        
    except Exception as e:
        frappe.logger().error(f"Error fetching attendance from CrossChex API: {str(e)}")
        return []

def sync_attendance_from_crosschex_cloud():
    """
    Entry point for scheduled sync job
    """
    try:
        result = manual_sync_crosschex_cloud()
        frappe.logger().info(f"CrossChex Cloud scheduled sync completed: {result}")
    except Exception as e:
        frappe.logger().error(f"CrossChex Cloud scheduled sync failed: {str(e)}")
        raise

@frappe.whitelist()
def get_sync_status():
    """
    Get current sync status
    """
    try:
        settings = frappe.get_single("Crosschex Settings")
        
        return {
            "last_sync": getattr(settings, "last_sync_time", "Never"),
            "last_status": getattr(settings, "last_sync_status", "No status"),
            "api_configured": bool(getattr(settings, "api_key", None)),
            "sync_enabled": getattr(settings, "enable_realtime_sync", False),
            "has_token": bool(getattr(settings, "token", None))
        }
        
    except Exception as e:
        return {"error": f"Error getting sync status: {str(e)}"}

@frappe.whitelist()
def test_api_connection(api_url=None, access_token=None):
    """
    Test the CrossChex Cloud API connection
    """
    try:
        settings = get_crosschex_settings()
        if not settings:
            return {"success": False, "error": "Crosschex Settings not configured"}
        
        # Test token generation
        token_result = generate_crosschex_token(settings.get("api_key"), settings.get("api_secret"))
        
        if token_result.get("success"):
            return {
                "success": True, 
                "message": "Connection successful! Token generated."
            }
        else:
            return {
                "success": False, 
                "error": f"Connection failed: {token_result.get('error')}"
            }
    
    except Exception as e:
        return {"success": False, "error": f"Connection test failed: {str(e)}"}