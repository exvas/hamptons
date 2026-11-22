"""
Regression checks for withdrawing a leave that has already ended
(hamptons/hamptons/doctype/leave_withdrawal_request/leave_withdrawal_request.py).

Uses real records, inside one transaction that is ALWAYS rolled back. frappe.db.commit is
replaced by a function that raises, so a commit anywhere in the code under test fails the
check instead of leaking data:

    bench --site <site> execute hamptons.tests.test_leave_withdrawal_ended.run --kwargs "{'worked': 'HR-LAP-2026-00278', 'not_worked': 'HR-LAP-2026-00294'}"
"""

import json

import frappe
from frappe.utils import getdate

from hamptons.hamptons.doctype.leave_withdrawal_request import leave_withdrawal_request as lwr


def run(worked, not_worked):
	frappe.set_user("Administrator")
	real_commit = frappe.db.commit

	def no_commit(*a, **k):
		raise RuntimeError("commit attempted during test")

	frappe.db.commit = no_commit
	results = []
	try:
		for check in (
			check_worked_leave_allowed,
			check_not_worked_leave_refused,
			check_rebuild_attendance,
			check_withdrawable_list,
		):
			frappe.db.savepoint("lwr_check")
			try:
				results.append(
					{"check": check.__name__, "status": "PASS", **(check(worked, not_worked) or {})}
				)
			except Exception as e:
				results.append(
					{
						"check": check.__name__,
						"status": "FAIL",
						"error": f"{type(e).__name__}: {frappe.utils.strip_html(str(e))}",
					}
				)
			finally:
				frappe.db.rollback(save_point="lwr_check")
				frappe.clear_messages()
	finally:
		frappe.db.commit = real_commit
		frappe.db.rollback()
	print(json.dumps(results, indent=2, default=str))
	if any(r["status"] != "PASS" for r in results):
		raise AssertionError("FAILED")
	return {"passed": len(results)}


def _request(leave_name):
	la = frappe.get_doc("Leave Application", leave_name)
	doc = frappe.new_doc("Leave Withdrawal Request")
	doc.update({"employee": la.employee, "leave_application": la.name, "reason": "test", "status": "Pending"})
	return la, doc


def check_worked_leave_allowed(worked, not_worked):
	la, doc = _request(worked)
	_assert(getdate(la.to_date) < getdate(), "test leave must have ended")
	_assert(lwr.get_leave_days_without_checkins(la) == [], "expected check-ins on every working day")
	doc.validate_leave_application()  # must not raise
	return {"leave": worked, "employee": la.employee}


def check_not_worked_leave_refused(worked, not_worked):
	la, doc = _request(not_worked)
	missing = lwr.get_leave_days_without_checkins(la)
	_assert(missing, "negative case must have days without check-ins")
	try:
		doc.validate_leave_application()
	except frappe.ValidationError as e:
		_assert("No check-ins found on" in str(e), f"unexpected message: {e}")
	else:
		raise AssertionError("ended leave without check-ins was accepted")
	return {"leave": not_worked, "missing_days": [str(d) for d in missing]}


def check_rebuild_attendance(worked, not_worked):
	"""Simulate the state after the leave is cancelled, then rebuild from check-ins."""
	la, doc = _request(worked)
	att = frappe.get_all(
		"Attendance",
		filters={"leave_application": worked, "docstatus": 1},
		fields=["name", "attendance_date"],
	)
	_assert(att, "leave has no attendance to cancel")
	for a in att:
		frappe.db.set_value("Attendance", a.name, "docstatus", 2, update_modified=False)
	# cancel_leave_application() runs before the rebuild in the real flow
	frappe.db.set_value(
		"Leave Application", worked, {"docstatus": 2, "status": "Cancelled"}, update_modified=False
	)

	doc.name = "LWR-TEST"
	doc.rebuild_attendance_for_past_days()

	rows = frappe.get_all(
		"Attendance",
		filters={
			"employee": la.employee,
			"attendance_date": ("between", [la.from_date, la.to_date]),
			"docstatus": ("<", 2),
		},
		fields=["attendance_date", "status", "in_time", "out_time"],
		order_by="attendance_date",
	)
	days = {getdate(a.attendance_date) for a in att}
	rebuilt = {getdate(r.attendance_date): r for r in rows}
	_assert(set(rebuilt) == days, f"rebuilt {sorted(rebuilt)} != leave days {sorted(days)}")
	_assert(all(r.status != "On Leave" for r in rebuilt.values()), "still On Leave")
	return {"rebuilt": {str(k): v.status for k, v in rebuilt.items()}}


def check_withdrawable_list(worked, not_worked):
	out = {}
	for name, expected in ((worked, True), (not_worked, False)):
		la = frappe.get_doc("Leave Application", name)
		user = frappe.db.get_value("Employee", la.employee, "user_id")
		_assert(user, f"{la.employee} has no user")
		frappe.set_user(user)
		try:
			names = [l.name for l in lwr.get_withdrawable_leaves()]
		finally:
			frappe.set_user("Administrator")
		_assert((name in names) == expected, f"{name} listed={name in names}, expected {expected}")
		out[name] = "listed" if expected else "not listed"
	return out


def _assert(cond, msg):
	if not cond:
		raise AssertionError(msg)
