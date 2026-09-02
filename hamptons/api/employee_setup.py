# Copyright (c) 2026, sammish and contributors
# For license information, please see license.txt

"""
Employee Setup API

Backs the "HR Actions > Setup New Employee" button on the Employee form.
One click creates, for an Active employee:

  1. Leave Policy Assignment (based on the active Leave Period). Submitting it
     makes HRMS create the Leave Allocations (the hamptons override skips leave
     types the employee is not eligible for - gender / nationality / religion).
  2. Shift Assignment for the shift chosen in the dialog.

Each step is independent and idempotent: an existing record is reported and
skipped, and a failure in one step never undoes the other step.
"""

import frappe
from frappe import _
from frappe.utils import cint, formatdate, getdate, today

LEAVE_STEP = "Leave Policy Assignment"
SHIFT_STEP = "Shift Assignment"


@frappe.whitelist()
def get_setup_status(employee: str) -> dict:
	"""What is already set up for the employee, plus defaults for the setup dialog."""
	frappe.has_permission("Employee", ptype="read", doc=employee, throw=True)
	emp = _get_employee(employee)

	leave_period = get_default_leave_period(emp.company)
	if leave_period:
		existing_lpa = get_overlapping_leave_policy_assignment(
			emp.name, leave_period.from_date, leave_period.to_date
		)
	else:
		existing_lpa = get_overlapping_leave_policy_assignment(emp.name, today(), today())

	existing_shift = get_active_shift_assignment(emp.name)

	pending = []
	if not existing_lpa:
		pending.append(LEAVE_STEP)
	if not existing_shift:
		pending.append(SHIFT_STEP)

	return {
		"employee": emp.name,
		"employee_name": emp.employee_name,
		"status": emp.status,
		"company": emp.company,
		"date_of_joining": emp.date_of_joining,
		"default_shift": emp.default_shift,
		"default_leave_policy": get_default_leave_policy(),
		"default_leave_period": leave_period,
		"leave_policy_assignment": existing_lpa,
		"shift_assignment": existing_shift,
		"pending": pending,
		"missing_attributes": get_missing_leave_attributes(emp.name),
	}


@frappe.whitelist()
def setup_new_employee(
	employee: str,
	shift_type: str | None = None,
	shift_start_date: str | None = None,
	leave_policy: str | None = None,
	leave_period: str | None = None,
) -> dict:
	"""Create the Leave Policy Assignment (+ Leave Allocations) and Shift Assignment.

	Returns a per-step result: {"status": "created" | "skipped" | "failed", "name", "message", ...}
	"""
	emp = _get_employee(employee)
	if emp.status != "Active":
		frappe.throw(
			_("Employee {0} is not Active (status: {1}). Setup is only for active employees.").format(
				frappe.bold(emp.name), emp.status
			)
		)

	# Fail fast before touching anything; insert()/submit() below enforce this again.
	frappe.has_permission(LEAVE_STEP, ptype="create", throw=True)
	frappe.has_permission(SHIFT_STEP, ptype="create", throw=True)

	leave_result = _run_step(
		lambda: _assign_leave_policy(emp, leave_policy, leave_period),
		savepoint="hamptons_setup_leave",
		context=f"{LEAVE_STEP} for {emp.name}",
	)
	shift_result = _run_step(
		lambda: _assign_shift(emp, shift_type, shift_start_date),
		savepoint="hamptons_setup_shift",
		context=f"{SHIFT_STEP} for {emp.name}",
	)

	return {
		"employee": emp.name,
		"employee_name": emp.employee_name,
		"leave_policy_assignment": leave_result,
		"leave_allocations": leave_result.pop("allocations", []),
		"shift_assignment": shift_result,
	}


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def _assign_leave_policy(emp, leave_policy=None, leave_period=None) -> dict:
	leave_policy = leave_policy or get_default_leave_policy()
	if not leave_policy:
		frappe.throw(
			_("Select a Leave Policy. There is not exactly one submitted Leave Policy to use by default.")
		)
	if not frappe.db.exists("Leave Policy", {"name": leave_policy, "docstatus": 1}):
		frappe.throw(_("Leave Policy {0} does not exist or is not submitted.").format(frappe.bold(leave_policy)))

	if leave_period:
		period = frappe.db.get_value(
			"Leave Period", leave_period, ["name", "from_date", "to_date", "is_active"], as_dict=True
		)
		if not period:
			frappe.throw(_("Leave Period {0} does not exist.").format(frappe.bold(leave_period)))
	else:
		period = get_default_leave_period(emp.company)
		if not period:
			frappe.throw(
				_("No active Leave Period for {0} covers today. Create a Leave Period first.").format(
					frappe.bold(emp.company)
				)
			)

	existing = get_overlapping_leave_policy_assignment(emp.name, period.from_date, period.to_date)
	if existing:
		return _step(
			"skipped",
			name=existing.name,
			message=_("Leave Policy {0} is already assigned for {1} to {2}.").format(
				existing.leave_policy, formatdate(existing.effective_from), formatdate(existing.effective_to)
			),
		)

	if getdate(emp.date_of_joining) > getdate(period.to_date):
		frappe.throw(
			_("Date of Joining {0} is after Leave Period {1} ends on {2}. Create a Leave Period for that year.").format(
				formatdate(emp.date_of_joining), frappe.bold(period.name), formatdate(period.to_date)
			)
		)

	# Re-use a matching draft (e.g. left behind by an earlier failed submit) instead of duplicating it.
	draft_name = frappe.db.get_value(
		LEAVE_STEP,
		{"employee": emp.name, "docstatus": 0, "leave_policy": leave_policy, "leave_period": period.name},
		"name",
	)
	if draft_name:
		doc = frappe.get_doc(LEAVE_STEP, draft_name)
	else:
		doc = frappe.new_doc(LEAVE_STEP)
		doc.employee = emp.name
		doc.leave_policy = leave_policy
		doc.carry_forward = cint(emp.get("custom_leave_carryforward_enabled"))

	doc.assignment_based_on = "Leave Period"
	doc.leave_period = period.name
	if doc.is_new():
		doc.insert()
	doc.submit()  # HRMS on_submit -> grant_leave_alloc_for_employee -> Leave Allocations

	allocations = frappe.get_all(
		"Leave Allocation",
		filters={"leave_policy_assignment": doc.name, "docstatus": 1},
		fields=["name", "leave_type", "new_leaves_allocated", "from_date", "to_date"],
		order_by="leave_type asc",
	)
	return _step(
		"created",
		name=doc.name,
		message=_("Leave Policy {0} assigned for {1} to {2}. {3} leave allocation(s) created.").format(
			leave_policy, formatdate(doc.effective_from), formatdate(doc.effective_to), len(allocations)
		),
		allocations=allocations,
		effective_from=doc.effective_from,
		effective_to=doc.effective_to,
	)


def _assign_shift(emp, shift_type=None, start_date=None) -> dict:
	existing = get_active_shift_assignment(emp.name)
	if existing:
		return _step(
			"skipped",
			name=existing.name,
			message=_("Shift {0} is already assigned from {1}.").format(
				existing.shift_type, formatdate(existing.start_date)
			),
		)

	if not shift_type:
		frappe.throw(_("Select which shift the employee will work."))
	if not frappe.db.exists("Shift Type", shift_type):
		frappe.throw(_("Shift Type {0} does not exist.").format(frappe.bold(shift_type)))

	start_date = getdate(start_date) if start_date else getdate(emp.date_of_joining or today())

	doc = frappe.new_doc(SHIFT_STEP)
	doc.employee = emp.name
	doc.company = emp.company
	doc.shift_type = shift_type
	doc.start_date = start_date
	doc.status = "Active"
	doc.insert()
	doc.submit()

	return _step(
		"created",
		name=doc.name,
		message=_("Shift {0} assigned from {1}.").format(shift_type, formatdate(start_date)),
		shift_type=shift_type,
		start_date=start_date,
	)


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def get_default_leave_policy() -> str | None:
	"""The submitted Leave Policy, when there is exactly one; otherwise None (user must pick)."""
	names = frappe.get_all("Leave Policy", filters={"docstatus": 1}, pluck="name", limit=2)
	return names[0] if len(names) == 1 else None


def get_default_leave_period(company: str, as_of=None):
	"""Active Leave Period of the company that covers `as_of` (default today)."""
	as_of = getdate(as_of or today())
	periods = frappe.get_all(
		"Leave Period",
		filters={
			"is_active": 1,
			"company": company,
			"from_date": ("<=", as_of),
			"to_date": (">=", as_of),
		},
		fields=["name", "from_date", "to_date"],
		order_by="from_date desc",
		limit=1,
	)
	return periods[0] if periods else None


def get_missing_leave_attributes(employee: str) -> list[str]:
	"""Employee fields the leave eligibility rules depend on that are still empty.
	Leave types restricted by these are skipped (not allocated) while they are unset."""
	labels = {"gender": _("Gender"), "custom_nationality": _("Nationality"), "custom_religion": _("Religion")}
	fields = [f for f in labels if frappe.db.has_column("Employee", f)]
	values = frappe.db.get_value("Employee", employee, fields, as_dict=True) or {}
	return [labels[f] for f in fields if not values.get(f)]


def get_overlapping_leave_policy_assignment(employee: str, from_date, to_date):
	"""Submitted Leave Policy Assignment overlapping [from_date, to_date] - the same rule HRMS
	uses in validate_policy_assignment_overlap, so we skip instead of hitting that error."""
	return frappe.db.get_value(
		LEAVE_STEP,
		{
			"employee": employee,
			"docstatus": 1,
			"effective_to": (">=", getdate(from_date)),
			"effective_from": ("<=", getdate(to_date)),
		},
		["name", "leave_policy", "effective_from", "effective_to", "leaves_allocated"],
		as_dict=True,
	)


def get_active_shift_assignment(employee: str, as_of=None):
	"""Submitted, Active Shift Assignment that is open-ended or ends on/after `as_of`."""
	as_of = getdate(as_of or today())
	sa = frappe.qb.DocType(SHIFT_STEP)
	rows = (
		frappe.qb.from_(sa)
		.select(sa.name, sa.shift_type, sa.start_date, sa.end_date)
		.where(
			(sa.employee == employee)
			& (sa.docstatus == 1)
			& (sa.status == "Active")
			& (sa.end_date.isnull() | (sa.end_date >= as_of))
		)
		.orderby(sa.start_date, order=frappe.qb.desc)
		.limit(1)
	).run(as_dict=True)
	return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_employee(employee: str):
	fields = ["name", "employee_name", "status", "company", "date_of_joining", "default_shift"]
	if frappe.db.has_column("Employee", "custom_leave_carryforward_enabled"):
		fields.append("custom_leave_carryforward_enabled")

	emp = frappe.db.get_value("Employee", employee, fields, as_dict=True)
	if not emp:
		frappe.throw(_("Employee {0} not found.").format(frappe.bold(employee)), frappe.DoesNotExistError)
	return emp


def _step(status: str, name: str | None = None, message: str = "", **extra) -> dict:
	return {"status": status, "name": name, "message": message, **extra}


def _run_step(step, savepoint: str, context: str) -> dict:
	"""Run one step inside a savepoint. On failure roll back only that step, drop the
	messages it queued (they describe a rolled-back document) and report the error."""
	messages_before = len(frappe.message_log)
	frappe.db.savepoint(savepoint)
	try:
		return step()
	except Exception as e:
		frappe.db.rollback(save_point=savepoint)
		del frappe.message_log[messages_before:]

		if isinstance(e, (frappe.ValidationError, frappe.PermissionError)):
			message = str(e)
		else:
			frappe.log_error(title=f"Employee Setup failed: {context}", message=frappe.get_traceback())
			message = _("Unexpected error: {0}. See Error Log.").format(str(e))

		return _step("failed", message=message)
