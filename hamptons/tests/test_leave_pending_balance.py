"""
Regression checks for validate_pending_leave_balance (hamptons/overrides/leave_application.py):
an employee cannot apply beyond the balance left after their other pending applications.

Runs on a real site inside one transaction that is ALWAYS rolled back:

    bench --site <site> execute hamptons.tests.test_leave_pending_balance.run
"""

import json

import frappe
from frappe.utils import add_days, getdate, today

from hrms.hr.doctype.leave_application.leave_application import InsufficientLeaveBalanceError

LEAVE_TYPE = "Annual Leave"


def run():
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	# The app's workflow notification senders call frappe.db.commit() after sendmail(now=True);
	# a commit would destroy the transaction this harness relies on, so stub them out.
	import hamptons.overrides.leave_application as override

	original_senders = (
		override._send_notification_to_hod,
		override._send_notification_to_employee,
		override._log_workflow_action,
	)
	override._send_notification_to_hod = lambda *a, **k: None
	override._send_notification_to_employee = lambda *a, **k: None
	override._log_workflow_action = lambda *a, **k: None  # Workflow Action Log insert commits too
	checks = [
		check_second_pending_application_beyond_balance_is_refused,
		check_application_within_remaining_balance_is_allowed,
		check_approval_ignores_other_pending_applications,
		check_rejected_application_is_not_counted,
	]
	results = []
	try:
		for check in checks:
			results.append(_run_check(check))
	finally:
		frappe.db.rollback()
		(
			override._send_notification_to_hod,
			override._send_notification_to_employee,
			override._log_workflow_action,
		) = original_senders
		frappe.flags.mute_emails = False
		frappe.set_user("Administrator")
	print(json.dumps(results, indent=2, default=str))
	failed = [r["check"] for r in results if r["status"] != "PASS"]
	if failed:
		raise AssertionError(f"FAILED: {', '.join(failed)}")
	return {"passed": len(results), "failed": 0}


def _run_check(check):
	frappe.db.savepoint("hamptons_pending_check")
	try:
		return {"check": check.__name__, "status": "PASS", **(check() or {})}
	except Exception as e:
		return {"check": check.__name__, "status": "FAIL", "error": f"{type(e).__name__}: {e}", "traceback": frappe.get_traceback()[-1200:]}
	finally:
		frappe.db.rollback(save_point="hamptons_pending_check")
		frappe.clear_messages()


# ---------------------------------------------------------------------------


def check_second_pending_application_beyond_balance_is_refused():
	"""Balance 10, first application 6 days pending -> second application of 6 days refused."""
	emp, start = _employee_with_allocation(10)
	first = _apply(emp, start, 6)
	_assert(first.docstatus == 0 and first.status == "Open", "first application should be pending")

	try:
		_apply(emp, add_days(start, 10), 6)
	except InsufficientLeaveBalanceError as e:
		_assert("pending approval" in str(e), f"unexpected message: {e}")
	else:
		raise AssertionError("second application beyond remaining balance was accepted")

	_assert(_open_days(emp) == 6, f"pending days changed: {_open_days(emp)}")
	return {"employee": emp, "first": first.name}


def check_application_within_remaining_balance_is_allowed():
	"""Balance 10, 6 pending -> 4 more days allowed, 5 refused."""
	emp, start = _employee_with_allocation(10)
	_apply(emp, start, 6)
	second = _apply(emp, add_days(start, 10), 4)
	_assert(second.name and _open_days(emp) == 10, f"pending days: {_open_days(emp)}")

	try:
		_apply(emp, add_days(start, 20), 1)
	except InsufficientLeaveBalanceError:
		pass
	else:
		raise AssertionError("application exceeding remaining balance by 1 day was accepted")
	return {"employee": emp, "pending_days": _open_days(emp)}


def check_approval_ignores_other_pending_applications():
	"""Approving (submitting) one application must not be blocked by another pending one."""
	emp, start = _employee_with_allocation(10)
	first = _apply(emp, start, 6)
	second = _apply(emp, add_days(start, 10), 4)

	first.status = "Approved"
	first.submit()  # standard HRMS check: 10 >= 6
	_assert(frappe.db.get_value("Leave Application", first.name, "docstatus") == 1, "first not submitted")

	second.reload()
	second.status = "Approved"
	second.submit()  # 10 - 6 = 4 >= 4
	_assert(frappe.db.get_value("Leave Application", second.name, "docstatus") == 1, "second not submitted")

	try:
		_apply(emp, add_days(start, 20), 1)
	except InsufficientLeaveBalanceError:
		pass
	else:
		raise AssertionError("application with zero balance left was accepted")
	return {"employee": emp, "approved": [first.name, second.name]}


def check_rejected_application_is_not_counted():
	"""A rejected application releases its reservation."""
	emp, start = _employee_with_allocation(10)
	first = _apply(emp, start, 6)
	first.status = "Rejected"
	first.save()
	second = _apply(emp, add_days(start, 10), 10)
	_assert(second.name, "full balance should be available after rejection")
	return {"employee": emp}


# ---------------------------------------------------------------------------


def _assert(condition, message):
	if not condition:
		raise AssertionError(message)


def _open_days(employee):
	return frappe.db.sql(
		"""select ifnull(sum(total_leave_days), 0) from `tabLeave Application`
		where employee = %s and leave_type = %s and docstatus = 0 and status = 'Open'""",
		(employee, LEAVE_TYPE),
	)[0][0]


def _employee_with_allocation(days):
	"""Temp employee with a submitted Annual Leave allocation for the rest of this year.
	Returns (employee name, first safe application date: 30+ days out, inside the allocation)."""
	template = frappe.db.get_value(
		"Employee",
		{"status": "Active", "holiday_list": ("is", "set")},
		["company", "holiday_list", "leave_approver"],
		as_dict=True,
	)
	_assert(template, "need an active employee with a holiday list to copy settings from")

	year_end = getdate(f"{getdate(today()).year}-12-31")
	emp = frappe.get_doc(
		{
			"doctype": "Employee",
			"employee_number": "ZZTEST-" + frappe.generate_hash(length=6).upper(),
			"first_name": "Pending",
			"last_name": "Balance",
			"gender": "Male",
			"date_of_birth": "1990-01-01",
			"date_of_joining": "2020-01-01",
			"company": template.company,
			"holiday_list": template.holiday_list,
			"leave_approver": template.leave_approver,
			"status": "Active",
		}
	).insert(ignore_permissions=True)

	alloc = frappe.get_doc(
		{
			"doctype": "Leave Allocation",
			"employee": emp.name,
			"leave_type": LEAVE_TYPE,
			"from_date": f"{year_end.year}-01-01",
			"to_date": year_end,
			"new_leaves_allocated": days,
		}
	).insert(ignore_permissions=True)
	alloc.submit()

	start = add_days(getdate(today()), 30)
	_assert(add_days(start, 40) <= year_end, "not enough room left in the year for the test dates")
	return emp.name, start


def _apply(employee, from_date, days):
	doc = frappe.get_doc(
		{
			"doctype": "Leave Application",
			"employee": employee,
			"leave_type": LEAVE_TYPE,
			"from_date": from_date,
			"to_date": add_days(from_date, days - 1),
			"status": "Open",
			"description": "pending balance test",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def cleanup_residue():
	"""Delete ZZTEST-* employees and everything hanging off them (only needed if a run leaked
	records because of a commit inside the code under test). Commits on return via bench execute."""
	deleted = []
	for emp in frappe.get_all("Employee", filters={"name": ("like", "ZZTEST-%")}, pluck="name"):
		for name in frappe.get_all("Leave Application", filters={"employee": emp}, pluck="name"):
			for log in frappe.get_all("Workflow Action Log", filters={"reference_name": name}, pluck="name"):
				frappe.delete_doc("Workflow Action Log", log, force=True, ignore_permissions=True)
			doc = frappe.get_doc("Leave Application", name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Leave Application", name, force=True, ignore_permissions=True)
			deleted.append(("Leave Application", name))
		for name in frappe.get_all("Leave Allocation", filters={"employee": emp}, pluck="name"):
			doc = frappe.get_doc("Leave Allocation", name)
			if doc.docstatus == 1:
				doc.cancel()
			for entry in frappe.get_all("Leave Ledger Entry", filters={"employee": emp}, pluck="name"):
				frappe.delete_doc("Leave Ledger Entry", entry, force=True, ignore_permissions=True)
			frappe.delete_doc("Leave Allocation", name, force=True, ignore_permissions=True)
			deleted.append(("Leave Allocation", name))
		frappe.delete_doc("Employee", emp, force=True, ignore_permissions=True)
		deleted.append(("Employee", emp))
	print(json.dumps(deleted))
	return {"deleted": len(deleted)}


def simulate_application(employee, from_date, days, leave_type=LEAVE_TYPE):
	"""Dry-run: try to save a draft application for a REAL employee and report the outcome.
	Rolled back, nothing is saved. bench --site X execute ...simulate_application --args '["1019","2026-11-01",1]'"""
	import hamptons.overrides.leave_application as override

	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	saved = (override._send_notification_to_hod, override._send_notification_to_employee, override._log_workflow_action)
	override._send_notification_to_hod = override._send_notification_to_employee = override._log_workflow_action = lambda *a, **k: None
	try:
		doc = _apply(employee, getdate(from_date), days) if leave_type == LEAVE_TYPE else None
		out = {"result": "ACCEPTED", "name": doc.name, "leave_balance": doc.leave_balance}
	except Exception as e:
		out = {"result": "REFUSED", "error_type": type(e).__name__, "message": frappe.utils.strip_html(str(e))}
	finally:
		frappe.db.rollback()
		override._send_notification_to_hod, override._send_notification_to_employee, override._log_workflow_action = saved
	print(json.dumps(out, default=str))
	return out
