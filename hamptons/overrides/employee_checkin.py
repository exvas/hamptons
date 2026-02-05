# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, get_datetime, now_datetime, time_diff_in_hours, get_time
from datetime import datetime, timedelta


def is_holiday_or_weekly_off(employee, check_date):
	"""
	Check if a date is a holiday or weekly off for an employee.

	Args:
		employee: Employee ID
		check_date: Date to check

	Returns:
		True if the date is a holiday or weekly off, False otherwise
	"""
	check_date = getdate(check_date)

	# Get employee's holiday list
	holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")

	if not holiday_list:
		# Try to get default holiday list from company
		company = frappe.db.get_value("Employee", employee, "company")
		if company:
			holiday_list = frappe.db.get_value("Company", company, "default_holiday_list")

	if not holiday_list:
		return False

	# Check if the date is in the holiday list (includes weekly_off days)
	is_holiday = frappe.db.exists(
		"Holiday",
		{
			"parent": holiday_list,
			"holiday_date": check_date
		}
	)

	return bool(is_holiday)


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
		shift_start_time: time object or timedelta for shift start
		grace_period_minutes: grace period in minutes

	Returns:
		Time difference as time object, or None if not late
	"""
	from datetime import time as dt_time

	checkin_date = getdate(checkin_time)
	checkin_datetime = get_datetime(checkin_time)

	# Handle shift_start_time - convert timedelta to time if needed
	# Frappe stores Time fields as timedelta internally
	if isinstance(shift_start_time, timedelta):
		total_seconds = int(shift_start_time.total_seconds())
		hours = total_seconds // 3600
		minutes = (total_seconds % 3600) // 60
		seconds = total_seconds % 60
		shift_start_time = dt_time(hours, minutes, seconds)
	elif not isinstance(shift_start_time, dt_time):
		shift_start_time = get_time(shift_start_time)

	# Create datetime for shift start on the checkin date
	shift_start_datetime = datetime.combine(checkin_date, shift_start_time)

	# Add grace period
	if grace_period_minutes:
		shift_start_datetime += timedelta(minutes=grace_period_minutes)

	# Compare - only calculate late time if employee arrived AFTER shift start
	if checkin_datetime > shift_start_datetime:
		time_diff = checkin_datetime - shift_start_datetime
		total_secs = time_diff.total_seconds()
		# Safety check: only return late time if positive
		if total_secs > 0:
			hours = int(total_secs // 3600)
			minutes = int((total_secs % 3600) // 60)
			seconds = int(total_secs % 60)
			return get_time(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

	return None


def calculate_early_exit_time(checkout_time, shift_end_time):
	"""
	Calculate how early an employee checked out compared to shift end time.

	Args:
		checkout_time: datetime of checkout
		shift_end_time: time object or timedelta for shift end

	Returns:
		Time difference as time object, or None if not early
	"""
	from datetime import time as dt_time

	checkout_date = getdate(checkout_time)
	checkout_datetime = get_datetime(checkout_time)

	# Handle shift_end_time - convert timedelta to time if needed
	# Frappe stores Time fields as timedelta internally
	if isinstance(shift_end_time, timedelta):
		total_seconds = int(shift_end_time.total_seconds())
		hours = total_seconds // 3600
		minutes = (total_seconds % 3600) // 60
		seconds = total_seconds % 60
		shift_end_time = dt_time(hours, minutes, seconds)
	elif not isinstance(shift_end_time, dt_time):
		shift_end_time = get_time(shift_end_time)

	# Create datetime for shift end on the checkout date
	shift_end_datetime = datetime.combine(checkout_date, shift_end_time)

	# Compare - only calculate early exit time if employee left BEFORE shift end
	if checkout_datetime < shift_end_datetime:
		time_diff = shift_end_datetime - checkout_datetime
		total_secs = time_diff.total_seconds()
		# Safety check: only return early time if positive
		if total_secs > 0:
			hours = int(total_secs // 3600)
			minutes = int((total_secs % 3600) // 60)
			seconds = int(total_secs % 60)
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
		# Convert shift_type.end_time from timedelta to time if needed
		from datetime import time as dt_time
		shift_end = shift_type.end_time
		if isinstance(shift_end, timedelta):
			total_seconds = int(shift_end.total_seconds())
			hours = total_seconds // 3600
			minutes = (total_seconds % 3600) // 60
			seconds = total_seconds % 60
			shift_end = dt_time(hours, minutes, seconds)
		elif not isinstance(shift_end, dt_time):
			shift_end = get_time(shift_end)

		# Create datetime for shift end on the checkin date
		shift_end_datetime = datetime.combine(checkin_date, shift_end)

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
		"status": "Pending"
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
	Hook to run after Employee Checkin is created (after_insert).

	IMPORTANT: This hook NO LONGER creates regularizations immediately.
	Instead, it only triggers consolidation for late-synced checkins.

	The 8 PM scheduler job handles all regularization creation because:
	1. Individual checkins don't show the full picture (IN without OUT yet)
	2. Biometric devices often mark all punches as "IN" regardless of actual type
	3. Creating regularization from individual checkins caused incorrect records
	   (e.g., treating 5 PM checkout marked as "IN" as a 9-hour late entry)

	Args:
		doc: Employee Checkin document
		method: Method name (not used)
	"""
	# Check if Attendance Regularization DocType exists on this site
	if not frappe.db.exists("DocType", "Attendance Regularization"):
		frappe.logger().info(
			f"Skipping regularization check for {doc.name}: DocType not found"
		)
		return

	checkin_date = getdate(doc.time)
	sync_date = getdate(doc.creation)

	# CRITICAL: Detect late-synced checkins (device was offline)
	# If punch date is before sync date, trigger full consolidation for that date
	if checkin_date < sync_date:
		frappe.logger().info(
			f"Late-synced checkin detected: {doc.name} | Punch: {checkin_date} | Synced: {sync_date}"
		)

		# Enqueue consolidation for the punch date in background
		frappe.enqueue(
			'hamptons.overrides.employee_checkin.consolidate_attendance_for_date',
			queue='short',
			timeout=300,
			processing_date=checkin_date,
			is_retry=True,
			now=False
		)

		frappe.logger().info(
			f"Queued consolidation for {checkin_date} due to late-synced checkin {doc.name}"
		)
		return

	# For same-day checkins: DO NOT create regularization immediately
	# The 8 PM scheduler job will handle this with full context
	# This prevents incorrect regularizations from individual checkins
	frappe.logger().debug(
		f"Checkin {doc.name} recorded. Regularization will be processed by scheduler at 8 PM."
	)


def daily_attendance_regularization_job():
	"""
	Consolidate daily checkins per employee and create Attendance or Attendance Regularization
	Runs daily at 11:45 PM via scheduler.
	"""
	# Check if Attendance Regularization DocType exists on this site
	if not frappe.db.exists("DocType", "Attendance Regularization"):
		frappe.logger().info(
			"Skipping daily attendance regularization job: DocType not found on this site"
		)
		return

	from frappe.utils import getdate
	consolidate_attendance_for_date(getdate())

@frappe.whitelist()
def run_attendance_regularization_sync(days: int = 365, include_yesterday: bool = True):
	"""
	Manually trigger attendance consolidation for a date range.
	Runs as a background job to avoid timeout.
	"""
	# Check if Attendance Regularization DocType exists on this site
	if not frappe.db.exists("DocType", "Attendance Regularization"):
		frappe.throw(_("Attendance Regularization DocType is not installed on this site"))

	from frappe.utils import getdate
	from datetime import timedelta

	# Enqueue the job to run in background
	frappe.enqueue(
		'hamptons.overrides.employee_checkin.process_attendance_sync_background',
		queue='long',
		timeout=3600,  # 1 hour timeout
		days=days,
		include_yesterday=include_yesterday,
		now=False
	)
	
	end_date = getdate() - timedelta(days=1) if include_yesterday else getdate()
	start_date = getdate() - timedelta(days=days)
	
	return {
		"success": True,
		"message": f"Background sync job started for {days} days (from {start_date} to {end_date})",
		"start_date": str(start_date),
		"end_date": str(end_date),
		"note": "Processing in background. Check Attendance Regularization list for results."
	}

def process_attendance_sync_background(days: int = 365, include_yesterday: bool = True):
	"""
	Background job to process attendance consolidation.
	This runs in a separate worker to avoid timeout.
	"""
	from frappe.utils import getdate
	from datetime import timedelta
	
	end_date = getdate() - timedelta(days=1) if include_yesterday else getdate()
	start_date = getdate() - timedelta(days=days)
	
	processed = 0
	error_count = 0
	summary = []
	cur = start_date
	
	while cur <= end_date:
		try:
			stats = consolidate_attendance_for_date(cur)
			processed += 1
			summary.append({"date": str(cur), **stats})
			
			# Commit every 10 days to avoid long transactions
			if processed % 10 == 0:
				frappe.db.commit()
				frappe.logger().info(f"Attendance sync: Processed {processed} days so far...")
		except Exception as e:
			error_count += 1
			frappe.log_error(message=str(e), title=f"Manual Regularization Sync Error - {cur}")
		cur = cur + timedelta(days=1)
	
	# Final commit
	frappe.db.commit()
	
	# Log completion
	frappe.logger().info(
		f"Attendance sync completed: {processed} days processed, {error_count} errors. "
		f"Range: {start_date} to {end_date}"
	)
	
	return {
		"success": True,
		"processed_days": processed,
		"errors": error_count,
		"start_date": str(start_date),
		"end_date": str(end_date)
	}


def consolidate_attendance_for_date(processing_date):
	"""
	Consolidate checkins for a specific date and create Attendance/Regularization per rules.
	Returns stats dict.
	"""
	# Check if Attendance Regularization DocType exists on this site
	if not frappe.db.exists("DocType", "Attendance Regularization"):
		frappe.logger().info(
			f"Skipping attendance consolidation for {processing_date}: Attendance Regularization DocType not found on this site"
		)
		return {"processed": 0, "created": 0, "updated": 0, "errors": 0}

	import json

	# Fetch all checkins for the day
	rows = frappe.db.sql(
		"""
		SELECT ec.name, ec.employee, ec.employee_name, ec.time, ec.log_type, ec.device_id
		FROM `tabEmployee Checkin` ec
		WHERE DATE(ec.time) = %s
		ORDER BY ec.employee, ec.time
		""",
		(processing_date,),
		as_dict=True
	)
	
	# Build map of employee -> list of checkins
	emp_checks = {}
	for r in rows:
		emp_checks.setdefault(r["employee"], []).append(r)
	
	# Get employees with active shift assignment today
	active_employees = frappe.db.sql(
		"""
		SELECT DISTINCT sa.employee, sa.shift_type
		FROM `tabShift Assignment` sa
		WHERE sa.docstatus = 1
		AND sa.start_date <= %s
		AND (sa.end_date IS NULL OR sa.end_date >= %s)
		""",
		(processing_date, processing_date),
		as_dict=True
	)
	
	created_attendance = 0
	created_regularizations = 0
	absents_marked = 0
	leaves_marked = 0
	
	for sa in active_employees:
		emp = sa["employee"]
		shift_type_name = sa["shift_type"]
		
		# Skip if attendance date is before employee's joining date
		emp_joining_date = frappe.db.get_value("Employee", emp, "date_of_joining")
		if emp_joining_date:
			# Ensure both are date objects for comparison
			emp_joining_date = getdate(emp_joining_date)
			if processing_date < emp_joining_date:
				continue
		
		shift_type = frappe.get_doc("Shift Type", shift_type_name)
		
		checks = emp_checks.get(emp, [])
		
		# No checkins -> mark based on approved leave or Absent
		# But first check if it's a holiday or weekly off - don't mark Absent on those days
		if not checks:
			try:
				# CRITICAL: Check if attendance already exists (from Attendance Request or other source)
				existing_att = frappe.db.exists(
					"Attendance",
					{"employee": emp, "attendance_date": processing_date, "docstatus": ["<", 2]}
				)
				if existing_att:
					# Attendance already exists (draft or submitted), skip
					continue

				# Check if this date is a holiday or weekly off for the employee
				is_holiday_or_weekoff = is_holiday_or_weekly_off(emp, processing_date)
				if is_holiday_or_weekoff:
					# Skip creating any attendance record for holidays/weekly offs
					continue

				# CRITICAL: Check for approved Attendance Request before marking Absent
				attendance_request = frappe.db.sql(
					"""
					SELECT name, reason, half_day
					FROM `tabAttendance Request`
					WHERE employee = %s
					AND docstatus = 1
					AND %s BETWEEN from_date AND to_date
					ORDER BY modified DESC
					LIMIT 1
					""",
					(emp, processing_date),
					as_dict=True
				)
				if attendance_request:
					ar = attendance_request[0]
					# Create attendance based on Attendance Request
					is_half_day = int(ar.get("half_day") or 0) == 1
					att_status = "Half Day" if is_half_day else "Present"
					attendance = frappe.get_doc({
						"doctype": "Attendance",
						"employee": emp,
						"attendance_date": processing_date,
						"shift": shift_type_name,
						"status": att_status,
						"attendance_request": ar.get("name"),
						"company": frappe.defaults.get_user_default("Company")
					})
					attendance.insert(ignore_permissions=True)
					attendance.submit()
					created_attendance += 1
					continue

				# Check approved leave for the day
				leave = frappe.db.sql(
					"""
					SELECT name, leave_type, half_day, half_day_date
					FROM `tabLeave Application`
					WHERE employee = %s
					AND docstatus = 1
					AND status IN ('Approved')
					AND %s BETWEEN from_date AND to_date
					ORDER BY modified DESC
					LIMIT 1
					""",
					(emp, processing_date),
					as_dict=True
				)
				if leave:
					la = leave[0]
					# Determine status: Half Day or On Leave
					is_half_day = int(la.get("half_day") or 0) == 1 and la.get("half_day_date") == processing_date
					att_status = "Half Day" if is_half_day else "On Leave"
					attendance = frappe.get_doc({
						"doctype": "Attendance",
						"employee": emp,
						"attendance_date": processing_date,
						"shift": shift_type_name,
						"status": att_status,
						"leave_type": la.get("leave_type"),
						"company": frappe.defaults.get_user_default("Company")
					})
					attendance.insert(ignore_permissions=True)
					attendance.submit()
					leaves_marked += 1
				else:
					attendance = frappe.get_doc({
						"doctype": "Attendance",
						"employee": emp,
						"attendance_date": processing_date,
						"shift": shift_type_name,
						"status": "Absent",
						"company": frappe.defaults.get_user_default("Company")
					})
					attendance.insert(ignore_permissions=True)
					attendance.submit()
					absents_marked += 1
			except Exception as e:
				frappe.log_error(message=str(e), title="Daily Attendance - Absent/Leave Creation Error")
			continue
		
		# Consolidate: Use time-based inference instead of relying on log_type
		# Many biometric devices mark all checkins as "IN", so we infer from time sequence
		from hamptons.overrides.attendance_utils import get_first_in_last_out
		first_in, last_out = get_first_in_last_out(checks, use_inferred=True)
		
		# Calculate late/early times using the new utility function
		from hamptons.overrides.attendance_utils import calculate_late_early_times

		first_in_time = first_in["time"] if first_in else None
		last_out_time = last_out["time"] if last_out else None

		result = calculate_late_early_times(first_in_time, last_out_time, shift_type, processing_date)
		needs_regularization = result['needs_regularization']
		late_time_val = result['late_time']

		late_enabled = bool(getattr(shift_type, "enable_late_entry_marking", False))

		# Regularization is needed if:
		# 1. Employee was late (beyond grace period)
		# 2. Employee left early (before shift end)
		# 3. Missing check-in or check-out
		# Only auto-mark Present if no issues detected

		try:
			# Avoid duplicates: if Attendance already exists for the date, skip creation
			existing_att = frappe.db.exists("Attendance", {"employee": emp, "attendance_date": processing_date, "docstatus": ["<", 2]})
			if existing_att:
				continue

			# Auto-mark Present if we have both IN and OUT and no issues
			if not needs_regularization and first_in and last_out:
				# Check if a draft regularization exists that shouldn't
				# This can happen if an earlier process created it incorrectly
				incorrect_reg = frappe.db.get_value(
					"Attendance Regularization",
					{"employee": emp, "posting_date": processing_date, "docstatus": 0},
					"name"
				)
				if incorrect_reg:
					# Delete the incorrect draft regularization
					frappe.delete_doc("Attendance Regularization", incorrect_reg, force=True)
					frappe.logger().info(
						f"Deleted incorrect draft regularization {incorrect_reg} for {emp} on {processing_date} - employee is on time"
					)

				# Auto mark Present
				attendance = frappe.get_doc({
					"doctype": "Attendance",
					"employee": emp,
					"employee_name": frappe.db.get_value("Employee", emp, "employee_name"),
					"attendance_date": processing_date,
					"shift": shift_type_name,
					"status": "Present",
					"company": frappe.defaults.get_user_default("Company")
				})
				attendance.insert(ignore_permissions=True)
				attendance.submit()
				created_attendance += 1
			else:
				# Check if a draft regularization already exists for employee/date
				existing_reg_name = frappe.db.get_value(
					"Attendance Regularization",
					{"employee": emp, "posting_date": processing_date, "docstatus": 0},
					"name"
				)

				if existing_reg_name:
					# UPDATE existing draft regularization with new checkin data
					# This handles late sync scenarios when machine was offline
					reg = frappe.get_doc("Attendance Regularization", existing_reg_name)

					# Get existing checkin names to avoid duplicates
					existing_checkin_names = set()
					for item in reg.attendance_regularization_item:
						if item.employee_checkin:
							existing_checkin_names.add(item.employee_checkin)

					# Add new checkin items that don't already exist
					items_added = False
					for c in [first_in, last_out]:
						if c and c["name"] not in existing_checkin_names:
							log_type = c.get("inferred_log_type", c.get("log_type", "IN"))
							reg.append("attendance_regularization_item", {
								"time": c["time"],
								"log_type": log_type,
								"device_id": c.get("device_id"),
								"employee_checkin": c["name"]
							})
							items_added = True

					# Update late time if there's an actual late value
					# Clear incorrect late values (like creation time) if employee is not late
					if late_time_val:
						if not reg.late or late_time_val != reg.late:
							reg.late = late_time_val
							items_added = True
					elif reg.late:
						# Employee is NOT late but late field has a value - clear it
						reg.late = None
						items_added = True

					if items_added:
						reg.save(ignore_permissions=True)
						frappe.logger().info(
							f"Updated existing regularization {existing_reg_name} for {emp} on {processing_date}"
						)
					continue

				# Check if a submitted regularization already exists (skip creation)
				existing_submitted = frappe.db.exists(
					"Attendance Regularization",
					{"employee": emp, "posting_date": processing_date, "docstatus": 1}
				)
				if existing_submitted:
					continue

				# Create new Attendance Regularization with consolidated items
				reg_data = {
					"doctype": "Attendance Regularization",
					"employee": emp,
					"employee_name": frappe.db.get_value("Employee", emp, "employee_name"),
					"posting_date": processing_date,
					"shift": shift_type_name,
					"start_time": shift_type.start_time,
					"end_time": shift_type.end_time,
					"status": "Pending"
				}
				# IMPORTANT: Only set 'late' field if there's an actual late time
				# Setting None causes Frappe Time field to use incorrect default
				if late_time_val:
					reg_data["late"] = late_time_val

				reg = frappe.get_doc(reg_data)
				# Add items: first IN and last OUT if they exist
				# Use inferred_log_type if available, otherwise fall back to log_type
				for c in [first_in, last_out]:
					if c:
						log_type = c.get("inferred_log_type", c.get("log_type", "IN"))
						reg.append("attendance_regularization_item", {
							"time": c["time"],
							"log_type": log_type,
							"device_id": c.get("device_id"),
							"employee_checkin": c["name"]
						})
				reg.insert(ignore_permissions=True)
				created_regularizations += 1
		except Exception as e:
			frappe.log_error(message=str(e), title="Daily Attendance - Creation Error")
			continue
	
	frappe.logger().info(
		f"Daily Attendance Summary {processing_date}: Present={created_attendance}, Regularizations={created_regularizations}, Absent={absents_marked}, OnLeave/HalfDay={leaves_marked}"
	)
	
	return {
		"present": created_attendance,
		"regularizations": created_regularizations,
		"absent": absents_marked,
		"leave": leaves_marked
	}
