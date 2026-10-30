"""
Run this in bench console:
bench --site hrms.hamptons.om console
"""

import json
import os

# Get app path
app_path = frappe.get_app_path("hamptons")  # noqa: F821

# Load workspace JSON
workspace_path = os.path.join(app_path, "hamptons", "workspace", "employee_checkin_dashboard.json")
with open(workspace_path) as f:
	workspace_data = json.load(f)

# Create or update workspace
if frappe.db.exists("Workspace", "Employee Check-in Dashboard"):  # noqa: F821
	doc = frappe.get_doc("Workspace", "Employee Check-in Dashboard")  # noqa: F821
	doc.update(workspace_data)
	doc.save()
	print("Workspace updated")
else:
	doc = frappe.get_doc(workspace_data)  # noqa: F821
	doc.insert()
	print("Workspace created")

frappe.db.commit()  # noqa: F821

# Install charts
chart_files = [
	"daily_check_ins_overview.json",
	"department_wise_attendance.json",
	"check_in_time_distribution.json",
]
chart_path = os.path.join(app_path, "hamptons", "dashboard_chart")

for chart_file in chart_files:
	with open(os.path.join(chart_path, chart_file)) as f:
		chart_data = json.load(f)

	chart_name = chart_data.get("name") or chart_data.get("chart_name")

	if frappe.db.exists("Dashboard Chart", chart_name):  # noqa: F821
		doc = frappe.get_doc("Dashboard Chart", chart_name)  # noqa: F821
		doc.update(chart_data)
		doc.save()
		print(f"Chart {chart_name} updated")
	else:
		doc = frappe.get_doc(chart_data)  # noqa: F821
		doc.insert()
		print(f"Chart {chart_name} created")

	frappe.db.commit()  # noqa: F821

print("✅ Dashboard installed successfully!")
