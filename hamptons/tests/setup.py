import frappe

# hamptons names departments without the company abbreviation (overrides/department.py), so ERPNext's
# own test records, which link to "_Test Department - _TC", find nothing. Create the departments
# under the names those records expect before any test record is built.
ERPNEXT_TEST_DEPARTMENTS = ("_Test Department - _TC", "_Test Department 1 - _TC")


def before_tests():
	frappe.flags.in_test = True
	root = frappe.db.get_value("Department", {"is_group": 1, "parent_department": ("in", ("", None))})
	company = "_Test Company" if frappe.db.exists("Company", "_Test Company") else None
	for name in ERPNEXT_TEST_DEPARTMENTS:
		if frappe.db.exists("Department", name):
			continue
		frappe.get_doc(
			{
				"doctype": "Department",
				"department_name": name,
				"parent_department": root,
				"company": company,
			}
		).insert(ignore_permissions=True)
	frappe.db.commit()
