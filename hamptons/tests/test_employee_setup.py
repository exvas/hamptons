"""
Regression checks for hamptons.api.employee_setup (Employee > HR Actions > Setup New Employee).

Runs against a real site inside one transaction that is ALWAYS rolled back, so it
leaves no records behind (temporary employees are created and discarded):

    bench --site <site> execute hamptons.tests.test_employee_setup.run

Needs on the site: a submitted Leave Policy, an active Leave Period covering today,
at least one Shift Type and the hamptons Employee custom fields (nationality / religion).
"""

import json

import frappe
from frappe.utils import add_days, date_diff, flt, getdate, rounded, today

from hamptons.api import employee_setup
from hamptons.overrides.leave_control_panel import check_leave_eligibility

LEAVE = employee_setup.LEAVE_STEP
SHIFT = employee_setup.SHIFT_STEP


def run():
	frappe.set_user("Administrator")
	checks = [
		check_form_script_loaded,
		check_fresh_employee_setup,
		check_rerun_is_idempotent,
		check_leave_restrictions_respected,
		check_inactive_employee_rejected,
		check_non_hr_user_rejected,
		check_hr_user_can_run,
	]
	results = []
	try:
		for check in checks:
			results.append(_run_check(check))
	finally:
		frappe.db.rollback()
		frappe.set_user("Administrator")
		for name in frappe.flags.get("hamptons_test_employees") or []:
			frappe.clear_document_cache("Employee", name)

	print(json.dumps(results, indent=2, default=str))
	failed = [r["check"] for r in results if r["status"] != "PASS"]
	if failed:
		raise AssertionError(f"FAILED: {', '.join(failed)}")
	return {"passed": len(results), "failed": 0}


def _run_check(check):
	frappe.db.savepoint("hamptons_setup_check")
	try:
		detail = check() or {}
		return {"check": check.__name__, "status": "PASS", **detail}
	except Exception as e:
		return {
			"check": check.__name__,
			"status": "FAIL",
			"error": f"{type(e).__name__}: {e}",
			"traceback": frappe.get_traceback()[-1500:],
		}
	finally:
		frappe.db.rollback(save_point="hamptons_setup_check")
		frappe.clear_messages()
		frappe.set_user("Administrator")


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_form_script_loaded():
	"""The doctype_js hook must put our script into the Employee form meta the desk loads."""
	from frappe.desk.form.meta import get_meta

	js = get_meta("Employee", cached=False).as_dict().get("__js") or ""
	_assert(
		"hamptons.api.employee_setup.setup_new_employee" in js and "HR Actions" in js,
		"hamptons/public/js/employee.js is not in Employee form meta __js (doctype_js hook / cache)",
	)
	return {"js_bytes": len(js)}


def check_fresh_employee_setup():
	ctx = _context()
	emp = _make_employee()

	before = employee_setup.get_setup_status(emp.name)
	_assert(before["pending"] == [LEAVE, SHIFT], f"expected both steps pending, got {before['pending']}")
	_assert(before["default_leave_period"]["name"] == ctx.period.name, "default leave period mismatch")

	result = employee_setup.setup_new_employee(
		emp.name,
		shift_type=ctx.shift_type,
		shift_start_date=str(emp.date_of_joining),
		leave_policy=ctx.policy,
		leave_period=ctx.period.name,
	)
	lpa, sa = result["leave_policy_assignment"], result["shift_assignment"]
	_assert(lpa["status"] == "created", f"LPA step: {lpa}")
	_assert(sa["status"] == "created", f"Shift step: {sa}")

	# Cross-check DB state independently of the returned dict
	lpa_row = frappe.db.get_value(
		LEAVE,
		lpa["name"],
		["docstatus", "leaves_allocated", "effective_from", "effective_to", "leave_period", "assignment_based_on"],
		as_dict=True,
	)
	_assert(lpa_row.docstatus == 1 and lpa_row.leaves_allocated == 1, f"LPA row: {lpa_row}")
	_assert(lpa_row.assignment_based_on == "Leave Period" and lpa_row.leave_period == ctx.period.name, f"LPA basis: {lpa_row}")
	_assert(
		getdate(lpa_row.effective_from) == getdate(ctx.period.from_date)
		and getdate(lpa_row.effective_to) == getdate(ctx.period.to_date),
		f"LPA dates {lpa_row.effective_from}..{lpa_row.effective_to} != period {ctx.period.from_date}..{ctx.period.to_date}",
	)

	allocations = frappe.get_all(
		"Leave Allocation",
		filters={"employee": emp.name, "docstatus": 1},
		fields=["leave_type", "new_leaves_allocated", "from_date", "to_date", "leave_policy_assignment"],
	)
	_assert(allocations, "no Leave Allocations were created")
	_assert(all(a.leave_policy_assignment == lpa["name"] for a in allocations), "allocation not linked to LPA")
	_assert(len(result["leave_allocations"]) == len(allocations), "returned allocation list != DB")
	by_type = {a.leave_type: a for a in allocations}

	# Mid-period joiner must be pro-rated exactly like HRMS calculate_pro_rated_leaves
	annual = frappe.db.get_value(
		"Leave Policy Detail", {"parent": ctx.policy, "leave_type": "Annual Leave"}, "annual_allocation"
	)
	if annual:
		expected = _expected_pro_rata(annual, emp.date_of_joining, ctx.period)
		_assert("Annual Leave" in by_type, "Annual Leave was not allocated")
		_assert(
			flt(by_type["Annual Leave"].new_leaves_allocated) == expected,
			f"Annual Leave: got {by_type['Annual Leave'].new_leaves_allocated}, expected pro-rata {expected}",
		)

	# Independent layer: ledger entries back every allocation
	ledger = frappe.db.count(
		"Leave Ledger Entry", {"employee": emp.name, "transaction_type": "Leave Allocation", "docstatus": 1}
	)
	_assert(ledger == len(allocations), f"ledger entries {ledger} != allocations {len(allocations)}")

	sa_row = frappe.db.get_value(
		SHIFT, sa["name"], ["docstatus", "status", "shift_type", "start_date", "end_date", "company"], as_dict=True
	)
	_assert(
		sa_row.docstatus == 1
		and sa_row.status == "Active"
		and sa_row.shift_type == ctx.shift_type
		and getdate(sa_row.start_date) == getdate(emp.date_of_joining)
		and not sa_row.end_date
		and sa_row.company == emp.company,
		f"Shift Assignment row: {sa_row}",
	)

	after = employee_setup.get_setup_status(emp.name)
	_assert(after["pending"] == [], f"still pending after setup: {after['pending']}")
	_assert(after["leave_policy_assignment"]["name"] == lpa["name"], "status does not report the new LPA")
	_assert(after["shift_assignment"]["name"] == sa["name"], "status does not report the new shift")

	return {
		"employee": emp.name,
		"date_of_joining": emp.date_of_joining,
		"lpa": lpa["name"],
		"allocations": {k: v.new_leaves_allocated for k, v in by_type.items()},
		"shift_assignment": sa["name"],
	}


def check_rerun_is_idempotent():
	ctx = _context()
	emp = _make_employee()
	args = dict(shift_type=ctx.shift_type, leave_policy=ctx.policy, leave_period=ctx.period.name)

	first = employee_setup.setup_new_employee(emp.name, **args)
	allocations_after_first = frappe.db.count("Leave Allocation", {"employee": emp.name, "docstatus": 1})

	second = employee_setup.setup_new_employee(emp.name, **args)
	_assert(
		second["leave_policy_assignment"]["status"] == "skipped"
		and second["leave_policy_assignment"]["name"] == first["leave_policy_assignment"]["name"],
		f"second LPA step: {second['leave_policy_assignment']}",
	)
	_assert(
		second["shift_assignment"]["status"] == "skipped"
		and second["shift_assignment"]["name"] == first["shift_assignment"]["name"],
		f"second shift step: {second['shift_assignment']}",
	)
	_assert(second["leave_allocations"] == [], "re-run reported new allocations")

	counts = {
		"lpa": frappe.db.count(LEAVE, {"employee": emp.name, "docstatus": ("<", 2)}),
		"shift": frappe.db.count(SHIFT, {"employee": emp.name, "docstatus": ("<", 2)}),
		"allocations": frappe.db.count("Leave Allocation", {"employee": emp.name, "docstatus": 1}),
	}
	_assert(counts["lpa"] == 1 and counts["shift"] == 1, f"duplicates created: {counts}")
	_assert(counts["allocations"] == allocations_after_first, f"allocation count changed: {counts}")
	return counts


def check_leave_restrictions_respected():
	"""Ineligible leave types (gender / nationality / religion) are skipped, eligible ones allocated."""
	ctx = _context()
	emp = _make_employee(gender="Female", custom_nationality="Non-Omani", custom_religion="Muslim")

	# Expected set must be computed BEFORE setup: once-in-service rules (Hajj Leave) report
	# "ineligible" as soon as an active allocation exists.
	policy_rows = frappe.get_all(
		"Leave Policy Detail", filters={"parent": ctx.policy}, fields=["leave_type", "annual_allocation"]
	)
	expected = set()
	for row in policy_rows:
		lt = frappe.db.get_value(
			"Leave Type", row.leave_type, ["is_lwp", "is_compensatory", "is_earned_leave"], as_dict=True
		)
		eligible, _reason = check_leave_eligibility(emp.name, row.leave_type)
		if not eligible or lt.is_lwp or lt.is_compensatory:
			continue
		if not lt.is_earned_leave and _expected_pro_rata(row.annual_allocation, emp.date_of_joining, ctx.period) == 0:
			continue  # HRMS skips zero allocations
		expected.add(row.leave_type)

	result = employee_setup.setup_new_employee(
		emp.name, shift_type=ctx.shift_type, leave_policy=ctx.policy, leave_period=ctx.period.name
	)
	_assert(result["leave_policy_assignment"]["status"] == "created", f"LPA: {result['leave_policy_assignment']}")

	allocated = set(frappe.get_all("Leave Allocation", filters={"employee": emp.name, "docstatus": 1}, pluck="leave_type"))
	_assert(allocated == expected, f"allocated {sorted(allocated)} != expected {sorted(expected)}")

	in_policy = {r.leave_type for r in policy_rows}
	spot_checks = {}
	for leave_type, should_have in (
		("Maternity Leave", True),
		("Hajj Leave", True),
		("Paternity Leave", False),
		("Caregiver leave", False),
		("Bereavement Leave - Wife (Non-Muslim Female)", False),
	):
		if leave_type in in_policy:
			_assert((leave_type in allocated) == should_have, f"{leave_type}: allocated={leave_type in allocated}, expected={should_have}")
			spot_checks[leave_type] = "allocated" if should_have else "skipped"

	return {"employee": emp.name, "allocated": sorted(allocated), "spot_checks": spot_checks}


def check_inactive_employee_rejected():
	ctx = _context()
	emp = _make_employee(status="Inactive")
	try:
		employee_setup.setup_new_employee(emp.name, shift_type=ctx.shift_type)
	except frappe.ValidationError as e:
		_assert("not Active" in str(e), f"unexpected message: {e}")
	else:
		raise AssertionError("inactive employee was set up")
	_assert(_nothing_created(emp.name), "records were created for an inactive employee")
	return {"employee": emp.name}


def check_non_hr_user_rejected():
	user = frappe.db.sql(
		"""select u.name from tabUser u
		where u.enabled = 1 and u.user_type = 'System User' and u.name not in ('Administrator', 'Guest')
		and not exists (select 1 from `tabHas Role` r where r.parent = u.name
			and r.role in ('HR Manager', 'HR User', 'System Manager', 'Administrator'))
		limit 1"""
	)
	if not user:
		return {"skipped": "no enabled non-HR system user on this site"}
	user = user[0][0]

	ctx = _context()
	emp = _make_employee()
	frappe.set_user(user)
	try:
		employee_setup.setup_new_employee(emp.name, shift_type=ctx.shift_type)
	except frappe.PermissionError:
		pass
	else:
		raise AssertionError(f"{user} without HR roles was allowed to run setup")
	finally:
		frappe.set_user("Administrator")
	_assert(_nothing_created(emp.name), "records were created despite missing permission")
	return {"user": user}


def check_hr_user_can_run():
	"""Real HR role (not Administrator) goes through the normal permission checks."""
	user = _find_unrestricted_hr_manager()
	if not user:
		return {"skipped": "no enabled HR Manager user without User Permissions on this site"}

	ctx = _context()
	emp = _make_employee()
	frappe.set_user(user)
	try:
		status = employee_setup.get_setup_status(emp.name)
		_assert(status["pending"] == [LEAVE, SHIFT], f"pending as {user}: {status['pending']}")
		result = employee_setup.setup_new_employee(
			emp.name, shift_type=ctx.shift_type, leave_policy=ctx.policy, leave_period=ctx.period.name
		)
	finally:
		frappe.set_user("Administrator")

	_assert(result["leave_policy_assignment"]["status"] == "created", f"LPA as {user}: {result['leave_policy_assignment']}")
	_assert(result["shift_assignment"]["status"] == "created", f"Shift as {user}: {result['shift_assignment']}")
	_assert(frappe.db.get_value(LEAVE, result["leave_policy_assignment"]["name"], "owner") == user, "LPA owner is not the HR user")
	_assert(frappe.db.get_value(SHIFT, result["shift_assignment"]["name"], "owner") == user, "Shift owner is not the HR user")
	return {"user": user, "lpa": result["leave_policy_assignment"]["name"], "shift": result["shift_assignment"]["name"]}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert(condition, message):
	if not condition:
		raise AssertionError(message)


def _context():
	periods = frappe.get_all(
		"Leave Period",
		filters={"is_active": 1, "from_date": ("<=", today()), "to_date": (">=", today())},
		fields=["name", "from_date", "to_date", "company"],
		order_by="from_date desc",
		limit=1,
	)
	_assert(periods, "no active Leave Period covering today")
	period = periods[0]

	policy = employee_setup.get_default_leave_policy() or frappe.db.get_value("Leave Policy", {"docstatus": 1}, "name")
	_assert(policy, "no submitted Leave Policy")

	shift_type = "8:00AM - 5:00PM" if frappe.db.exists("Shift Type", "8:00AM - 5:00PM") else frappe.db.get_value("Shift Type", {}, "name")
	_assert(shift_type, "no Shift Type")

	return frappe._dict(period=period, company=period.company, policy=policy, shift_type=shift_type)


def _make_employee(**overrides):
	ctx = _context()
	# joined 30 days ago (inside the period) so allocations must be pro-rated
	date_of_joining = max(getdate(ctx.period.from_date), add_days(getdate(today()), -30))
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"employee_number": "ZZTEST-" + frappe.generate_hash(length=6).upper(),
			"first_name": "Setup",
			"last_name": "Test",
			"gender": "Male",
			"date_of_birth": "1990-01-01",
			"date_of_joining": date_of_joining,
			"company": ctx.company,
			"status": "Active",
			"custom_nationality": "Omani",
			"custom_religion": "Muslim",
		}
	)
	doc.update(overrides)
	doc.insert(ignore_permissions=True)
	frappe.flags.setdefault("hamptons_test_employees", []).append(doc.name)
	return doc


def _expected_pro_rata(annual_allocation, date_of_joining, period):
	"""Same arithmetic as hrms ...leave_policy_assignment.calculate_pro_rated_leaves (non-earned)."""
	if getdate(date_of_joining) <= getdate(period.from_date):
		return flt(annual_allocation)
	actual = date_diff(period.to_date, date_of_joining) + 1
	complete = date_diff(period.to_date, period.from_date) + 1
	return min(rounded(annual_allocation * actual / complete), flt(annual_allocation))


def _find_unrestricted_hr_manager():
	"""Enabled HR Manager (not Administrator) with no User Permission rows, so the check
	exercises role permissions only. Deterministic order so reruns pick the same user."""
	users = frappe.get_all(
		"Has Role", filters={"role": "HR Manager", "parenttype": "User"}, pluck="parent", order_by="parent asc"
	)
	for user in users:
		if user == "Administrator" or not frappe.db.get_value("User", user, "enabled"):
			continue
		if frappe.db.exists("User Permission", {"user": user}):
			continue
		return user
	return None


def _nothing_created(employee):
	return (
		frappe.db.count(LEAVE, {"employee": employee}) == 0
		and frappe.db.count(SHIFT, {"employee": employee}) == 0
		and frappe.db.count("Leave Allocation", {"employee": employee}) == 0
	)

