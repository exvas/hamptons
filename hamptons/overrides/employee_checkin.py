# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, get_datetime, now_datetime, time_diff_in_hours, get_time
from datetime import datetime, timedelta


def get_active_shift_assignment(employee, date=None):
	"""
	Get the active Shift Assignment for an employee on a specific date.
	If multiple assignments exist, returns the one with the most recent start date.
	
	Args:
		employee: Employee ID
		date: Date to check (defaults to today)
	
	Returns:
		Shift Assignment document or None
	"""
	if not date:
		date = getdate()
	
	# Query for active shift assignments on the given date
	shift_assignments = frappe.db.sql("""
		SELECT name, shift_type, start_date, end_date
		FROM `tabShift Assignment`
		WHERE employee = %s
		AND docstatus = 1
		AND (
			(start_date <= %s AND (end_date IS NULL OR end_date >= %s))
		)
		ORDER BY start_date DESC
		LIMIT 1
	""", (employee, date, date), as_dict=1)
	
	if shift_assignments:
		return frappe.get_doc("Shift Assignment", shift_assignments[0].name)
	
	return None


def validate_shift_type(shift_type_name):
	"""
	Validate that the Shift Type has valid Start Time and End Time values.
	
	Args:
		shift_type_name: Name of the Shift Type
	
	Returns:
		Shift Type document
	
	Raises:
		ValidationError if shift type is invalid
	"""
	shift_type = frappe.get_doc("Shift Type", shift_type_name)
	
	if not shift_type.start_time:
		frappe.throw(_("Shift Type {0} does not have a valid Start Time").format(shift_type_name))
	
	if not shift_type.end_time:
		frappe.throw(_("Shift Type {0} does not have a valid End Time").format(shift_type_name))
	
	return shift_type


def calculate_late_time(checkin_time, shift_start_time, grace_period_minutes=0):
	"""
	Calculate how late an employee is based on checkin time and shift start time.
	
	Args:
		checkin_time: datetime of checkin
		shift_start_time: time object for shift start
		grace_period_minutes: grace period in minutes
	
	Returns:
		Time difference as time object, or None if not late
	"""
	checkin_date = getdate(checkin_time)
	
	# Create datetime for shift start on the checkin date
	shift_start_datetime = datetime.combine(checkin_date, shift_start_time)
	
	# Add grace period
	if grace_period_minutes:
		shift_start_datetime += timedelta(minutes=grace_period_minutes)
	
	# Compare
	if checkin_time > shift_start_datetime:
		time_diff = checkin_time - shift_start_datetime
		hours = int(time_diff.total_seconds() // 3600)
		minutes = int((time_diff.total_seconds() % 3600) // 60)
		seconds = int(time_diff.total_seconds() % 60)
		return get_time(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
	
	return None


def calculate_early_exit_time(checkout_time, shift_end_time):
	"""
	Calculate how early an employee checked out compared to shift end time.
	
	Args:
		checkout_time: datetime of checkout
		shift_end_time: time object for shift end
	
	Returns:
		Time difference as time object, or None if not early
	"""
	checkout_date = getdate(checkout_time)
	
	# Create datetime for shift end on the checkout date
	shift_end_datetime = datetime.combine(checkout_date, shift_end_time)
	
	# Compare
	if checkout_time < shift_end_datetime:
		time_diff = shift_end_datetime - checkout_time
		hours = int(time_diff.total_seconds() // 3600)
		minutes = int((time_diff.total_seconds() % 3600) // 60)
		seconds = int(time_diff.total_seconds() % 60)
		return get_time(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
	
	return None


def should_create_regularization(checkin_doc):
	"""
	Determine if an Attendance Regularization should be created based on checkin/checkout.
	Creates regularization immediately for late entries, and after shift end for early exits.
	
	Args:
		checkin_doc: Employee Checkin document
	
	Returns:
		tuple (should_create: bool, reason: str, late_time: time or None)
	"""
	# Get active shift assignment
	checkin_date = getdate(checkin_doc.time)
	shift_assignment = get_active_shift_assignment(checkin_doc.employee, checkin_date)
	
	if not shift_assignment:
		return False, "No active shift assignment found", None
	
	# Validate shift type
	try:
		shift_type = validate_shift_type(shift_assignment.shift_type)
	except Exception as e:
		frappe.log_error(message=str(e), title="Shift Type Validation Error")
		return False, str(e), None
	
	current_time = now_datetime()
	checkin_datetime = get_datetime(checkin_doc.time)
	
	# Check for late entry (IN log) - Create immediately
	if checkin_doc.log_type == "IN":
		grace_period = shift_type.late_entry_grace_period or 0
		late_time = calculate_late_time(checkin_datetime, shift_type.start_time, grace_period)
		
		if late_time:
			return True, "Late entry", late_time
	
	# Check for early exit (OUT log) - Only after shift end time
	elif checkin_doc.log_type == "OUT":
		# Create datetime for shift end on the checkin date
		shift_end_datetime = datetime.combine(checkin_date, shift_type.end_time)
		
		# Only proceed if shift end time has passed
		if current_time < shift_end_datetime:
			return False, "Shift end time has not passed yet (early exit detection deferred)", None
		
		early_time = calculate_early_exit_time(checkin_datetime, shift_type.end_time)
		
		if early_time:
			return True, "Early exit", early_time
	
	return False, "No regularization needed", None


def create_or_update_attendance_regularization(checkin_doc, shift_assignment, shift_type, late_time):
	"""
	Create or update an Attendance Regularization document for the employee checkin.
	Now works with the new structure where one regularization can have multiple checkins.
	
	Args:
		checkin_doc: Employee Checkin document
		shift_assignment: Shift Assignment document
		shift_type: Shift Type document
		late_time: Time difference as time object
	"""
	# Check if checkin already has a regularization
	existing_reg = frappe.db.get_value("Attendance Regularization Item",
									   {"employee_checkin": checkin_doc.name},
									   "parent")
	
	if existing_reg:
		frappe.log_error(
			message=f"Checkin {checkin_doc.name} already linked to regularization {existing_reg}",
			title="Duplicate Regularization Attempt"
		)
		return
	
	checkin_date = getdate(checkin_doc.time)
	
	# Check if regularization exists for this employee and date
	existing_regularizations = frappe.db.get_all(
		"Attendance Regularization",
		filters={
			"employee": checkin_doc.employee,
			"posting_date": checkin_date,
			"docstatus": ["!=", 2]
		},
		fields=["name", "docstatus"]
	)
	
	if existing_regularizations:
		# Check if any are in draft status (docstatus = 0)
		draft_regularizations = [r for r in existing_regularizations if r.docstatus == 0]
		
		if draft_regularizations:
			# Add to existing draft regularization
			regularization = frappe.get_doc("Attendance Regularization", draft_regularizations[0].name)
			
			# Add new checkin item
			regularization.append("attendance_regularization_item", {
				"time": checkin_doc.time,
				"log_type": checkin_doc.log_type,
				"device_id": checkin_doc.device_id if hasattr(checkin_doc, 'device_id') else None,
				"employee_checkin": checkin_doc.name
			})
			
			# Update late time if this checkin is later
			if late_time and (not regularization.late or late_time > regularization.late):
				regularization.late = late_time
			
			regularization.save(ignore_permissions=True)
			
			# Update the checkin with regularization reference
			frappe.db.set_value("Employee Checkin", checkin_doc.name,
								"custom_attendance_regularization", regularization.name)
			
			frappe.msgprint(_("Added checkin to existing Attendance Regularization {0}").format(
				regularization.name
			))
			return
		else:
			# All regularizations are submitted/cancelled, log this
			frappe.log_error(
				message=f"All regularizations for {checkin_doc.employee} on {checkin_date} are submitted/cancelled",
				title="Cannot Add to Regularization"
			)
			return
	
	# Create new regularization document
	regularization = frappe.get_doc({
		"doctype": "Attendance Regularization",
		"employee": checkin_doc.employee,
		"employee_name": checkin_doc.employee_name,
		"posting_date": checkin_date,
		"log_type": checkin_doc.log_type,
		"shift": shift_type.name,
		"start_time": shift_type.start_time,
		"end_time": shift_type.end_time,
		"late": late_time,
		"status": "Open"
	})
	
	# Get reports_to from employee
	employee = frappe.get_doc("Employee", checkin_doc.employee)
	if employee.reports_to:
		regularization.reports_to = employee.reports_to
	
	# Add checkin item
	regularization.append("attendance_regularization_item", {
		"time": checkin_doc.time,
		"log_type": checkin_doc.log_type,
		"device_id": checkin_doc.device_id if hasattr(checkin_doc, 'device_id') else None,
		"employee_checkin": checkin_doc.name
	})
	
	regularization.insert(ignore_permissions=True)
	
	# Update the checkin with regularization reference
	frappe.db.set_value("Employee Checkin", checkin_doc.name,
						"custom_attendance_regularization", regularization.name)
	
	frappe.msgprint(_("Attendance Regularization {0} created for {1}").format(
		regularization.name, checkin_doc.employee_name
	))


def on_employee_checkin_submit(doc, method=None):
	"""
	Hook to run after Employee Checkin is submitted.
	Checks if attendance regularization should be created or updated.
	
	Args:
		doc: Employee Checkin document
		method: Method name (not used)
	"""
	# Check if regularization should be created
	should_create, reason, late_time = should_create_regularization(doc)
	
	if not should_create:
		frappe.log_error(
			message=f"Regularization not created for {doc.name}: {reason}",
			title="Attendance Regularization Check"
		)
		return
	
	# Get shift assignment and shift type
	checkin_date = getdate(doc.time)
	shift_assignment = get_active_shift_assignment(doc.employee, checkin_date)
	
	if not shift_assignment:
		frappe.log_error(
			message=f"No shift assignment found for {doc.employee} on {checkin_date}",
			title="Attendance Regularization - No Shift Assignment"
		)
		return
	
	shift_type = validate_shift_type(shift_assignment.shift_type)
	
	# Create or update regularization
	try:
		create_or_update_attendance_regularization(doc, shift_assignment, shift_type, late_time)
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(message=str(e), title="Attendance Regularization Creation Error")
		frappe.throw(_("Failed to create Attendance Regularization: {0}").format(str(e)))