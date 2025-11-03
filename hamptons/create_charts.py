# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe

def create_dashboard_charts():
	"""
	Create dashboard charts for Employee Check-in Dashboard
	Run using: bench --site [site] execute hamptons.create_charts.create_dashboard_charts
	"""
	
	# Chart 1: Daily Check-ins Overview (Time Series)
	chart1_data = {
		"doctype": "Dashboard Chart",
		"chart_name": "Daily Check-ins Overview",
		"chart_type": "Count",
		"document_type": "Employee Checkin",
		"based_on": "time",
		"value_based_on": "",
		"timespan": "Last Month",
		"time_interval": "Daily",
		"filters_json": "[]",
		"timeseries": 1,
		"group_by_type": "",
		"group_by_based_on": "",
		"number_of_groups": 0,
		"is_public": 1,
		"module": "Hamptons",
		"type": "Line",
		"custom_options": '{"colors": ["#29CD42"]}',
		"use_report_chart": 0
	}
	
	# Chart 2: Check-ins by Type (Pie Chart)
	chart2_data = {
		"doctype": "Dashboard Chart",
		"chart_name": "Checkins By Type",
		"chart_type": "Group By",
		"document_type": "Employee Checkin",
		"based_on": "",
		"value_based_on": "",
		"timespan": "",
		"time_interval": "",
		"filters_json": '[[\"Employee Checkin\",\"time\",\"Timespan\",\"last month\",false]]',
		"timeseries": 0,
		"group_by_type": "Count",
		"group_by_based_on": "log_type",
		"number_of_groups": 0,
		"is_public": 1,
		"module": "Hamptons",
		"type": "Pie",
		"custom_options": '{"colors": ["#29CD42", "#FF5858"]}',
		"use_report_chart": 0
	}
	
	# Chart 3: Check-ins This Week
	chart3_data = {
		"doctype": "Dashboard Chart",
		"chart_name": "Checkins This Week",
		"chart_type": "Count",
		"document_type": "Employee Checkin",
		"based_on": "time",
		"value_based_on": "",
		"timespan": "Last Week",
		"time_interval": "Daily",
		"filters_json": "[]",
		"timeseries": 1,
		"group_by_type": "",
		"group_by_based_on": "",
		"number_of_groups": 0,
		"is_public": 1,
		"module": "Hamptons",
		"type": "Bar",
		"custom_options": '{"colors": ["#5E64FF"]}',
		"use_report_chart": 0
	}
	
	# Chart 4: Check-in Time Distribution (Daily - Last Week)
	chart4_data = {
		"doctype": "Dashboard Chart",
		"chart_name": "Check-in Time Distribution",
		"chart_type": "Count",
		"document_type": "Employee Checkin",
		"based_on": "time",
		"value_based_on": "",
		"timespan": "Last Week",
		"time_interval": "Daily",
		"filters_json": '[[\"Employee Checkin\",\"log_type\",\"=\",\"IN\",false]]',
		"timeseries": 1,
		"group_by_type": "",
		"group_by_based_on": "",
		"number_of_groups": 0,
		"is_public": 1,
		"module": "Hamptons",
		"type": "Bar",
		"custom_options": '{"colors": ["#FF6C37"]}',
		"use_report_chart": 0
	}
	
	# Chart 5: Department-wise Attendance
	chart5_data = {
		"doctype": "Dashboard Chart",
		"chart_name": "Department-wise Attendance",
		"chart_type": "Group By",
		"document_type": "Employee Checkin",
		"based_on": "",
		"value_based_on": "",
		"timespan": "",
		"time_interval": "",
		"filters_json": '[[\"Employee Checkin\",\"time\",\"Timespan\",\"last month\",false]]',
		"timeseries": 0,
		"group_by_type": "Count",
		"group_by_based_on": "employee",
		"number_of_groups": 10,
		"is_public": 1,
		"module": "Hamptons",
		"type": "Donut",
		"custom_options": '{"colors": ["#5E64FF", "#29CD42", "#FF5858", "#FFA00A", "#A463F2", "#FF6C37"]}',
		"use_report_chart": 0
	}
	
	charts = [
		("Daily Check-ins Overview", chart1_data),
		("Checkins By Type", chart2_data),
		("Checkins This Week", chart3_data),
		("Check-in Time Distribution", chart4_data),
		("Department-wise Attendance", chart5_data)
	]
	
	created_count = 0
	updated_count = 0
	
	for chart_name, chart_data in charts:
		try:
			if frappe.db.exists("Dashboard Chart", chart_name):
				print(f"Updating chart: {chart_name}...")
				doc = frappe.get_doc("Dashboard Chart", chart_name)
				doc.update(chart_data)
				doc.save(ignore_permissions=True)
				updated_count += 1
				print(f"✓ Chart '{chart_name}' updated successfully")
			else:
				print(f"Creating chart: {chart_name}...")
				doc = frappe.get_doc(chart_data)
				doc.insert(ignore_permissions=True)
				created_count += 1
				print(f"✓ Chart '{chart_name}' created successfully")
			
			frappe.db.commit()
			
		except Exception as e:
			print(f"✗ Error with chart '{chart_name}': {str(e)}")
			frappe.db.rollback()
			import traceback
			traceback.print_exc()
	
	print("\n" + "="*60)
	print("📊 Dashboard Charts Summary")
	print("="*60)
	print(f"✓ Created: {created_count}")
	print(f"✓ Updated: {updated_count}")
	print("\n📋 Available Charts:")
	print("   1. Daily Check-ins Overview (Line Chart)")
	print("   2. Checkins By Type (Pie Chart - IN vs OUT)")
	print("   3. Checkins This Week (Bar Chart)")
	print("   4. Check-in Time Distribution (Hourly Bar Chart)")
	print("   5. Department-wise Attendance (Donut Chart)")
	print("\n🔗 Next Steps:")
	print("   1. Go to your Hamptons Workspace: /app/hamptons")
	print("   2. Click 'Edit' (pencil icon)")
	print("   3. Click '+ Add Chart' and select the charts above")
	print("   4. Add shortcuts and number cards as needed")
	print("   5. Click 'Save'")
	print("\n✅ All done! Charts are ready to add to your workspace.")
	print("="*60)
	
	return f"Created: {created_count}, Updated: {updated_count}"
