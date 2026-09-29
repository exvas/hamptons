"""
Regression checks for the medical certificate rule on Sick Leave / Caregiver leave
(hamptons/overrides/leave_application.py). Runs on a real site inside one transaction that is
ALWAYS rolled back:

    bench --site <site> execute hamptons.tests.test_medical_certificate.run
"""

import json

import frappe
from frappe.utils import add_days, getdate, today

from hamptons.tests.test_leave_pending_balance import _run_check, _assert

CERT_TYPES = ("Sick Leave", "Caregiver leave")


def run():
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	import hamptons.overrides.leave_application as override

	saved = (override._send_notification_to_hod, override._send_notification_to_employee, override._log_workflow_action)
	override._send_notification_to_hod = override._send_notification_to_employee = override._log_workflow_action = lambda *a, **k: None
	checks = [
		check_desk_save_without_certificate_refused,
		check_desk_save_with_certificate_field_allowed,
		check_mobile_insert_allowed_then_approval_blocked_until_attached,
		check_annual_leave_unaffected,
	]
	results = []
	try:
		for check in checks:
			results.append(_run_check(check))
	finally:
		frappe.db.rollback()
		override._send_notification_to_hod, override._send_notification_to_employee, override._log_workflow_action = saved
		frappe.local.form_dict.pop("cmd", None)
		frappe.flags.mute_emails = False
	print(json.dumps(results, indent=2, default=str))
	failed = [r["check"] for r in results if r["status"] != "PASS"]
	if failed:
		raise AssertionError(f"FAILED: {', '.join(failed)}")
	return {"passed": len(results), "failed": 0}


def check_desk_save_without_certificate_refused():
	emp, start = _employee()
	out = {}
	for i, leave_type in enumerate(CERT_TYPES):
		try:
			_apply(emp, leave_type, add_days(start, i * 10), 1)
		except frappe.ValidationError as e:
			_assert("medical certificate" in str(e).lower(), f"{leave_type}: unexpected message {e}")
			out[leave_type] = "refused"
		else:
			raise AssertionError(f"{leave_type} saved from desk without a certificate")
	return out


def check_desk_save_with_certificate_field_allowed():
	emp, start = _employee()
	url = _existing_file_url()
	out = {}
	for i, leave_type in enumerate(CERT_TYPES):
		doc = _apply(emp, leave_type, add_days(start, i * 10), 1, custom_medical_certificate=url)
		doc.status = "Approved"
		doc.submit()
		out[leave_type] = doc.name
	return out


def check_mobile_insert_allowed_then_approval_blocked_until_attached():
	"""Mobile app: insert first (no certificate possible), attachment uploaded right after."""
	emp, start = _employee()
	frappe.local.form_dict.cmd = "frappe.client.insert"
	try:
		doc = _apply(emp, "Sick Leave", start, 1)
	finally:
		frappe.local.form_dict.pop("cmd", None)
	_assert(doc.docstatus == 0 and not doc.custom_medical_certificate, "mobile insert should be a draft without certificate")

	# HOD tries to approve before any attachment -> blocked
	doc.status = "Approved"
	try:
		doc.submit()
	except frappe.ValidationError as e:
		_assert("medical certificate" in str(e).lower(), f"unexpected message: {e}")
	else:
		raise AssertionError("approved a mobile Sick Leave with no certificate")
	doc.reload()
	_assert(doc.docstatus == 0, "should still be draft")

	# The mobile app now uploads the attachment (File attached to the doc) -> field auto-filled
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_url": _existing_file_url(),
			"attached_to_doctype": "Leave Application",
			"attached_to_name": doc.name,
			"is_private": 1,
		}
	).insert(ignore_permissions=True)
	filled = frappe.db.get_value("Leave Application", doc.name, "custom_medical_certificate")
	_assert(filled == file_doc.file_url, f"certificate field not auto-filled from attachment: {filled}")

	doc.reload()
	doc.status = "Approved"
	doc.submit()
	_assert(frappe.db.get_value("Leave Application", doc.name, "docstatus") == 1, "not approved after attaching")
	return {"application": doc.name, "certificate": filled}


def check_annual_leave_unaffected():
	emp, start = _employee()
	doc = _apply(emp, "Annual Leave", start, 1)
	return {"application": doc.name}


# ---------------------------------------------------------------------------


def _existing_file_url():
	url = frappe.db.get_value("File", {"is_private": 1, "is_folder": 0, "file_url": ("like", "/private/files/%")}, "file_url")
	_assert(url, "need an existing private file to reference")
	return url


def _employee():
	template = frappe.db.get_value(
		"Employee", {"status": "Active", "holiday_list": ("is", "set")}, ["company", "holiday_list", "leave_approver"], as_dict=True
	)
	year_end = getdate(f"{getdate(today()).year}-12-31")
	emp = frappe.get_doc(
		{
			"doctype": "Employee",
			"employee_number": "ZZTEST-" + frappe.generate_hash(length=6).upper(),
			"first_name": "Cert",
			"last_name": "Test",
			"gender": "Male",
			"date_of_birth": "1990-01-01",
			"date_of_joining": "2020-01-01",
			"company": template.company,
			"holiday_list": template.holiday_list,
			"leave_approver": template.leave_approver,
			"status": "Active",
			"custom_nationality": "Omani",  # Caregiver leave is Omani-only
			"custom_religion": "Muslim",
		}
	).insert(ignore_permissions=True)
	for leave_type in ("Sick Leave", "Caregiver leave", "Annual Leave"):
		alloc = frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": emp.name,
				"leave_type": leave_type,
				"from_date": f"{year_end.year}-01-01",
				"to_date": year_end,
				"new_leaves_allocated": 10,
			}
		).insert(ignore_permissions=True)
		alloc.submit()
	start = add_days(getdate(today()), 30)
	_assert(add_days(start, 20) <= year_end, "not enough room left in the year")
	return emp.name, start


def _apply(employee, leave_type, from_date, days, **extra):
	doc = frappe.get_doc(
		{
			"doctype": "Leave Application",
			"employee": employee,
			"leave_type": leave_type,
			"from_date": from_date,
			"to_date": add_days(from_date, days - 1),
			"status": "Open",
			"description": "certificate test",
			**extra,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc
