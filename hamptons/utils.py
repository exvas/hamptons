# Copyright (c) 2024, sammish and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime, add_days
from datetime import timedelta


def cleanup_old_logs():
	"""
	Delete error logs and deleted files older than 15 days.
	This function is called by the scheduler every 5 days.
	
	Returns:
		dict: Result containing success status, counts, and cutoff date
	"""
	try:
		cutoff_date = add_days(now_datetime(), -15)
		
		# Delete old Error Logs
		error_logs_deleted = delete_old_error_logs(cutoff_date)
		
		# Delete old Deleted Documents
		deleted_docs_removed = delete_old_deleted_documents(cutoff_date)
		
		# Commit the changes
		frappe.db.commit()
		
		# Log the cleanup activity
		frappe.logger().info(
			f"Cleanup completed: {error_logs_deleted} error logs and {deleted_docs_removed} deleted documents removed"
		)
		
		return {
			"success": True,
			"error_logs_deleted": error_logs_deleted,
			"deleted_documents_removed": deleted_docs_removed,
			"cutoff_date": cutoff_date
		}
		
	except Exception as e:
		frappe.logger().error(f"Error during cleanup: {str(e)}")
		frappe.log_error(
			message=str(e),
			title="Cleanup Old Logs Error"
		)
		return {
			"success": False,
			"error": str(e)
		}


def delete_old_error_logs(cutoff_date):
	"""
	Delete Error Log entries older than the cutoff date.
	
	Args:
		cutoff_date: datetime object representing the cutoff date
	
	Returns:
		int: Number of error logs deleted
	"""
	try:
		# Get count before deletion
		old_logs = frappe.db.sql("""
			SELECT name 
			FROM `tabError Log`
			WHERE creation < %s
		""", (cutoff_date,), as_dict=1)
		
		count = len(old_logs)
		
		if count > 0:
			# Delete in batches to avoid long-running queries
			batch_size = 500
			for i in range(0, count, batch_size):
				batch = old_logs[i:i+batch_size]
				names = [log.name for log in batch]
				
				frappe.db.sql("""
					DELETE FROM `tabError Log`
					WHERE name IN ({})
				""".format(','.join(['%s'] * len(names))), tuple(names))
				
				frappe.db.commit()
			
			frappe.logger().info(f"Deleted {count} error logs older than {cutoff_date}")
		
		return count
		
	except Exception as e:
		frappe.logger().error(f"Error deleting old error logs: {str(e)}")
		raise


def delete_old_deleted_documents(cutoff_date):
	"""
	Delete Deleted Document entries older than the cutoff date.
	
	Args:
		cutoff_date: datetime object representing the cutoff date
	
	Returns:
		int: Number of deleted documents removed
	"""
	try:
		# Get count before deletion
		old_deleted_docs = frappe.db.sql("""
			SELECT name 
			FROM `tabDeleted Document`
			WHERE creation < %s
		""", (cutoff_date,), as_dict=1)
		
		count = len(old_deleted_docs)
		
		if count > 0:
			# Delete in batches to avoid long-running queries
			batch_size = 500
			for i in range(0, count, batch_size):
				batch = old_deleted_docs[i:i+batch_size]
				names = [doc.name for doc in batch]
				
				frappe.db.sql("""
					DELETE FROM `tabDeleted Document`
					WHERE name IN ({})
				""".format(','.join(['%s'] * len(names))), tuple(names))
				
				frappe.db.commit()
			
			frappe.logger().info(f"Deleted {count} deleted documents older than {cutoff_date}")
		
		return count
		
	except Exception as e:
		frappe.logger().error(f"Error deleting old deleted documents: {str(e)}")
		raise


@frappe.whitelist()
def manual_cleanup():
	"""
	Manual cleanup trigger that can be called from the UI.
	Returns a user-friendly message about the cleanup results.
	
	Returns:
		dict: Result with success status and message/error
	"""
	result = cleanup_old_logs()
	
	if result.get("success"):
		return {
			"success": True,
			"message": f"Cleanup completed successfully. Removed {result['error_logs_deleted']} error logs and {result['deleted_documents_removed']} deleted documents older than {result['cutoff_date'].strftime('%Y-%m-%d %H:%M:%S')}"
		}
	else:
		return {
			"success": False,
			"error": result.get("error", "Unknown error occurred")
		}


@frappe.whitelist()
def delete_all_error_logs():
	"""
	Delete ALL error logs regardless of age.
	Use with caution - this will remove all error logs from the system.
	
	Returns:
		dict: Result with success status and count of deleted logs
	"""
	try:
		# Get total count
		total_count = frappe.db.count("Error Log")
		
		if total_count == 0:
			return {
				"success": True,
				"message": "No error logs found to delete",
				"count": 0
			}
		
		# Delete all error logs
		frappe.db.sql("DELETE FROM `tabError Log`")
		frappe.db.commit()
		
		frappe.logger().info(f"Deleted all {total_count} error logs")
		
		return {
			"success": True,
			"message": f"Successfully deleted all {total_count} error logs",
			"count": total_count
		}
		
	except Exception as e:
		frappe.logger().error(f"Error deleting all error logs: {str(e)}")
		frappe.log_error(
			message=str(e),
			title="Delete All Error Logs Error"
		)
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def test_crosschex_sync_for_hamptons3():
	"""
	Test CrossChex sync for HAMTONS 3 configuration (API Key: 853cfe14ff50623d550056a72f829036)
	Returns detailed diagnostic information
	"""
	import json
	
	try:
		# Get the API configuration
		config = frappe.db.get_value(
			"CrossChex API Configuration",
			{"api_key": "853cfe14ff50623d550056a72f829036"},
			["name", "configuration_name", "api_url", "api_key", "connection_status", "last_sync_time"],
			as_dict=True
		)
		
		if not config:
			return {"success": False, "error": "Configuration not found for API Key 853cfe14ff50623d550056a72f829036"}
		
		# Check current checkin count
		before_count = frappe.db.count("Employee Checkin")
		
		# Test the sync
		from hamptons.hamptons.doctype.crosschex_settings.crosschex_settings import sync_individual_device
		
		result = sync_individual_device(
			api_url=config['api_url'],
			api_key=config['api_key'],
			config_row_name=config['name'],
			config_name=config['configuration_name']
		)
		
		# Check new checkin count
		after_count = frappe.db.count("Employee Checkin")
		new_checkins = after_count - before_count
		
		# Get recent checkins
		recent = frappe.db.sql("""
			SELECT employee, employee_name, time, log_type, device_id
			FROM `tabEmployee Checkin`
			ORDER BY time DESC
			LIMIT 5
		""", as_dict=True)
		
		return {
			"success": True,
			"config": config,
			"sync_result": result,
			"stats": {
				"before_count": before_count,
				"after_count": after_count,
				"new_checkins": new_checkins
			},
			"recent_checkins": recent
		}
		
	except Exception as e:
		frappe.log_error(
			message=str(e),
			title="CrossChex Sync Test Error"
		)
		return {
			"success": False,
			"error": str(e)
		}
