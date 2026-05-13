import frappe
from frappe import _
from frappe.utils import getdate, today

from erpnext.setup.doctype.employee.employee import get_all_employee_emails, get_employee_email


def send_work_anniversary_reminders():
	"""
	Override of hrms.controllers.employee_reminders.send_work_anniversary_reminders
	that explicitly excludes non-Active employees (Left, Suspended, etc.).

	The standard HRMS function already filters by status='Active', but this override
	provides an extra safety layer for Hamptons.
	"""
	to_send = int(frappe.db.get_single_value("HR Settings", "send_work_anniversary_reminders"))
	if not to_send:
		return

	sender = frappe.db.get_single_value("HR Settings", "sender_email")
	employees_joined_today = get_active_employees_with_anniversary_today()

	# Work anniversary email reminders are disabled
	return


def get_active_employees_with_anniversary_today():
	"""Get Active employees whose work anniversary falls today, grouped by company."""
	from collections import defaultdict

	employees = frappe.db.sql(
		"""
		SELECT `personal_email`, `company`, `company_email`, `user_id`,
			   `employee_name` AS 'name', `image`, `date_of_joining`
		FROM `tabEmployee`
		WHERE
			DAY(date_of_joining) = DAY(%(today)s)
			AND MONTH(date_of_joining) = MONTH(%(today)s)
			AND YEAR(date_of_joining) < YEAR(%(today)s)
			AND `status` = 'Active'
		""",
		dict(today=today()),
		as_dict=True,
	)

	grouped = defaultdict(list)
	for emp in employees:
		grouped[emp.get("company")].append(emp)

	return grouped


def get_work_anniversary_reminder_text(anniversary_persons):
	from frappe.utils import comma_sep

	if len(anniversary_persons) == 1:
		person_name = anniversary_persons[0]["name"]
		completed_years = getdate().year - anniversary_persons[0]["date_of_joining"].year
		year_label = _("year") if completed_years == 1 else _("years")
		return _("Today {0} completed {1} {2} at our Company! 🎉").format(
			_(person_name), completed_years, year_label
		)

	names_grouped_by_years = {}
	for person in anniversary_persons:
		completed_years = getdate().year - person["date_of_joining"].year
		names_grouped_by_years.setdefault(completed_years, []).append(person["name"])

	person_names_with_years = [
		_("{0} completed {1} {2}").format(
			comma_sep(person_names, _("{0} & {1}"), False),
			years,
			_("year") if years == 1 else _("years"),
		)
		for years, person_names in names_grouped_by_years.items()
	]

	anniversary_person = comma_sep(person_names_with_years, _("{0} & {1}"), False)
	return _("Today {0} at our Company! 🎉").format(_(anniversary_person))
