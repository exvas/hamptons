# Copyright (c) 2026, sammish and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "employee",
			"label": _("Employee ID"),
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "employee_name",
			"label": _("Employee Full Name"),
			"fieldtype": "Data",
			"width": 230
		},
		{
			"fieldname": "date_of_birth",
			"label": _("Date of Birth"),
			"fieldtype": "Date",
			"width": 120
		},
		{
			"fieldname": "date_of_joining",
			"label": _("Date of Joining"),
			"fieldtype": "Date",
			"width": 140
		},
		{
			"fieldname": "department",
			"label": _("Department"),
			"fieldtype": "Link",
			"options": "Department",
			"width": 180
		},
		{
			"fieldname": "designation",
			"label": _("Designation"),
			"fieldtype": "Link",
			"options": "Designation",
			"width": 180
		},
		{
			"fieldname": "branch",
			"label": _("Branch"),
			"fieldtype": "Link",
			"options": "Branch",
			"width": 150
		},
		{
			"fieldname": "custom_nationality",
			"label": _("Nationality"),
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "reports_to_name",
			"label": _("Reports To"),
			"fieldtype": "Data",
			"width": 180
		},
		{
			"fieldname": "custom_religion",
			"label": _("Religion"),
			"fieldtype": "Data",
			"width": 120
		},
	]


def get_data(filters):
	conditions = get_conditions(filters)

	data = frappe.db.sql("""
		SELECT
			e.name as employee,
			e.employee_name,
			e.date_of_birth,
			e.date_of_joining,
			e.department,
			e.designation,
			e.branch,
			e.custom_nationality,
			r.employee_name as reports_to_name,
			e.custom_religion
		FROM `tabEmployee` e
		LEFT JOIN `tabEmployee` r ON r.name = e.reports_to
		WHERE e.status = 'Active'
		{conditions}
		ORDER BY e.name
	""".format(conditions=conditions), filters, as_dict=1)

	return data


def get_conditions(filters):
	conditions = []

	if filters.get("department"):
		conditions.append("e.department = %(department)s")

	if filters.get("designation"):
		conditions.append("e.designation = %(designation)s")

	if filters.get("branch"):
		conditions.append("e.branch = %(branch)s")

	if filters.get("employee"):
		conditions.append("e.name = %(employee)s")

	if filters.get("nationality"):
		conditions.append("e.custom_nationality = %(nationality)s")

	if filters.get("religion"):
		conditions.append("e.custom_religion = %(religion)s")

	if filters.get("reports_to"):
		conditions.append("e.reports_to = %(reports_to)s")

	return " AND " + " AND ".join(conditions) if conditions else ""
