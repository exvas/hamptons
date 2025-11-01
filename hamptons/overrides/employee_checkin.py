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
	Hook to run after Employee Checkin is created (after_insert).
	Checks if attendance regularization should be created or updated.
	
	Note: Despite the function name, this runs on 'after_insert' to support
	automatic checkin creation from CrossChex sync.
	
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


def daily_attendance_regularization_job():
	"""
	Consolidate daily checkins per employee and create Attendance or Attendance Regularization
	Runs daily at 11:45 PM via scheduler.
	"""
	from frappe.utils import getdate
	consolidate_attendance_for_date(getdate())

@frappe.whitelist()
def run_attendance_regularization_sync(days: int = 365, include_yesterday: bool = True):
	"""
	Manually trigger attendance consolidation for a date range.
	Runs as a background job to avoid timeout.
	"""
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
	import json
	
	# Fetch all checkins for the day
	rows = frappe.db.sql(
		"""
		SELECT ec.name, ec.employee, ec.employee_name, ec.time, ec.log_type
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
		if emp_joining_date and processing_date < emp_joining_date:
			continue
		
		shift_type = frappe.get_doc("Shift Type", shift_type_name)
		
		checks = emp_checks.get(emp, [])
		
		# No checkins -> mark based on approved leave or Absent
		if not checks:
			try:
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
		
		# Consolidate: first IN, last OUT
		first_in = next((c for c in checks if c["log_type"] == "IN"), None)
		last_out = next((c for c in reversed(checks) if c["log_type"] == "OUT"), None)
		
		# Determine late/early logic
		late_enabled = bool(getattr(shift_type, "enable_late_entry_marking", False))
		grace = int(getattr(shift_type, "late_entry_grace_period", 0) or 0)
		
		needs_regularization = False
		late_time_val = None
		
		from datetime import datetime, timedelta, time as dt_time
		from frappe.utils import get_time
		
		if first_in:
			# Check late against shift start + grace
			# Ensure shift_type.start_time is a time object, not timedelta
			start_time = shift_type.start_time
			if isinstance(start_time, timedelta):
				# Convert timedelta to time (assuming it's seconds from midnight)
				total_seconds = int(start_time.total_seconds())
				hours = total_seconds // 3600
				minutes = (total_seconds % 3600) // 60
				seconds = total_seconds % 60
				start_time = get_time(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
			elif not isinstance(start_time, dt_time):
				start_time = get_time(start_time)
			
			shift_start_dt = datetime.combine(processing_date, start_time)
			shift_start_dt += timedelta(minutes=grace)
			first_in_dt = frappe.utils.get_datetime(first_in["time"])
			if first_in_dt > shift_start_dt:
				if not late_enabled:
					needs_regularization = True
				else:
					# keep late value for record
					diff = first_in_dt - shift_start_dt
					late_time_val = get_time(f"{int(diff.total_seconds()//3600):02d}:{int((diff.total_seconds()%3600)//60):02d}:{int(diff.total_seconds()%60):02d}")
		
		if last_out:
			# Early exit if before end time
			# Ensure shift_type.end_time is a time object, not timedelta
			end_time = shift_type.end_time
			if isinstance(end_time, timedelta):
				# Convert timedelta to time (assuming it's seconds from midnight)
				total_seconds = int(end_time.total_seconds())
				hours = total_seconds // 3600
				minutes = (total_seconds % 3600) // 60
				seconds = total_seconds % 60
				end_time = get_time(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
			elif not isinstance(end_time, dt_time):
				end_time = get_time(end_time)
			
			shift_end_dt = datetime.combine(processing_date, end_time)
			last_out_dt = frappe.utils.get_datetime(last_out["time"])
			if last_out_dt < shift_end_dt:
				needs_regularization = True
		
		# Edge cases: only IN or only OUT
		if not first_in or not last_out:
			needs_regularization = True
		
		try:
			# Avoid duplicates: if Attendance already exists for the date, skip creation
			existing_att = frappe.db.exists("Attendance", {"employee": emp, "attendance_date": processing_date, "docstatus": ["<", 2]})
			if existing_att:
				continue
			
			if not needs_regularization and first_in and last_out:
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
				# Skip if a regularization already exists for employee/date
				existing_reg = frappe.db.exists("Attendance Regularization", {"employee": emp, "posting_date": processing_date, "docstatus": ["<", 2]})
				if existing_reg:
					continue
				# Create Attendance Regularization with consolidated items
				reg = frappe.get_doc({
					"doctype": "Attendance Regularization",
					"employee": emp,
					"employee_name": frappe.db.get_value("Employee", emp, "employee_name"),
					"posting_date": processing_date,
					"shift": shift_type_name,
					"start_time": shift_type.start_time,
					"end_time": shift_type.end_time,
					"late": late_time_val,
					"status": "Pending"
				})
				# Add items: first IN and last OUT if they exist
				for c in [first_in, last_out]:
					if c:
						reg.append("attendance_regularization_item", {
							"time": c["time"],
							"log_type": c["log_type"],
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
