# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
import os


def install_dashboard():
	"""
	Install the Employee Check-in Dashboard workspace and charts
	Run using: bench --site [site] execute hamptons.install_utils.install_dashboard
	"""
	
	app_path = frappe.get_app_path('hamptons')
	
	# Install Dashboard Charts FIRST (workspace references them)
	chart_files = [
		'daily_check_ins_overview.json',
		'department_wise_attendance.json',
		'check_in_time_distribution.json'
	]
	
	chart_path = os.path.join(app_path, 'hamptons', 'dashboard_chart')
	
	for chart_file in chart_files:
		frappe.logger().info(f"Installing chart: {chart_file}...")
		print(f"Installing chart: {chart_file}...")
		try:
			with open(os.path.join(chart_path, chart_file), 'r') as f:
				chart_data = json.load(f)
			
			chart_name = chart_data.get('name') or chart_data.get('chart_name')
			
			# Check if chart already exists
			if frappe.db.exists('Dashboard Chart', chart_name):
				frappe.logger().info(f"  Chart '{chart_name}' already exists, updating...")
				doc = frappe.get_doc('Dashboard Chart', chart_name)
				doc.update(chart_data)
				doc.save(ignore_permissions=True)
			else:
				frappe.logger().info(f"  Creating new chart '{chart_name}'...")
				doc = frappe.get_doc(chart_data)
				doc.insert(ignore_permissions=True)
			
			frappe.db.commit()
			frappe.logger().info(f"  ✓ Chart installed successfully")
			print(f"✓ Chart '{chart_name}' installed successfully")
		except Exception as e:
			frappe.logger().error(f"  ✗ Error installing chart: {str(e)}")
			print(f"✗ Error installing chart: {str(e)}")
			frappe.db.rollback()
	
	# Install Workspace AFTER charts are created
	frappe.logger().info("Installing Employee Check-in Dashboard Workspace...")
	workspace_path = os.path.join(app_path, 'hamptons', 'workspace', 'employee_checkin_dashboard.json')
	
	try:
		with open(workspace_path, 'r') as f:
			workspace_data = json.load(f)
		
		# Remove references to non-existent links to avoid validation errors
		# We'll add them later if needed
		if 'links' in workspace_data:
			# Filter out links that might not exist
			valid_links = []
			for link in workspace_data.get('links', []):
				# Keep card breaks and links to core doctypes
				if link.get('type') == 'Card Break' or link.get('link_to') in ['Employee Checkin', 'Attendance Regularization', 'Shift Assignment', 'Shift Type']:
					valid_links.append(link)
			workspace_data['links'] = valid_links
		
		# Check if workspace already exists
		if frappe.db.exists('Workspace', 'Employee Check-in Dashboard'):
			frappe.logger().info("  Workspace already exists, updating...")
			doc = frappe.get_doc('Workspace', 'Employee Check-in Dashboard')
			doc.update(workspace_data)
			doc.save(ignore_permissions=True)
		else:
			frappe.logger().info("  Creating new workspace...")
			doc = frappe.get_doc(workspace_data)
			doc.insert(ignore_permissions=True)
		
		frappe.db.commit()
		frappe.logger().info("  ✓ Workspace installed successfully")
		print("✓ Workspace installed successfully")
	except Exception as e:
		frappe.logger().error(f"  ✗ Error installing workspace: {str(e)}")
		print(f"✗ Error installing workspace: {str(e)}")
		frappe.db.rollback()
		raise
	
	print("\n✅ Dashboard installation complete!")
	print("Access it at: /app/employee-check-in-dashboard")
	
	return "Dashboard installed successfully"


def install_simple_workspace():
	"""
	Install a simple Employee Check-in Dashboard workspace without charts
	Run using: bench --site [site] execute hamptons.install_utils.install_simple_workspace
	"""
	
	# Create a simple workspace
	workspace_data = {
		"doctype": "Workspace",
		"name": "Employee Check-in Dashboard",
		"title": "Employee Check-in Dashboard",
		"module": "Hamptons",
		"icon": "time",
		"is_hidden": 0,
		"public": 1,
		"content": '[{"id":"header1","type":"header","data":{"text":"<span class=\\"h4\\">Employee Check-in Dashboard</span>","col":12}},{"id":"shortcut1","type":"shortcut","data":{"shortcut_name":"Employee Checkin","col":3}},{"id":"shortcut2","type":"shortcut","data":{"shortcut_name":"Attendance Regularization","col":3}},{"id":"shortcut3","type":"shortcut","data":{"shortcut_name":"Shift Assignment","col":3}},{"id":"shortcut4","type":"shortcut","data":{"shortcut_name":"Employee Checkin Report","col":3}}]',
		"links": [
			{
				"type": "Card Break",
				"label": "Documents"
			},
			{
				"type": "Link",
				"link_type": "DocType",
				"link_to": "Employee Checkin",
				"label": "Employee Checkin"
			},
			{
				"type": "Link",
				"link_type": "DocType",
				"link_to": "Attendance Regularization",
				"label": "Attendance Regularization"
			},
			{
				"type": "Link",
				"link_type": "DocType",
				"link_to": "Shift Assignment",
				"label": "Shift Assignment"
			},
			{
				"type": "Card Break",
				"label": "Reports"
			},
			{
				"type": "Link",
				"link_type": "Report",
				"link_to": "Employee Checkin Report",
				"label": "Employee Checkin Report",
				"is_query_report": 1
			}
		],
		"shortcuts": [
			{
				"type": "DocType",
				"link_to": "Employee Checkin",
				"label": "Employee Checkin",
				"color": "Blue"
			},
			{
				"type": "DocType",
				"link_to": "Attendance Regularization",
				"label": "Attendance Regularization",
				"color": "Orange"
			},
			{
				"type": "DocType",
				"link_to": "Shift Assignment",
				"label": "Shift Assignment",
				"color": "Green"
			},
			{
				"type": "Report",
				"link_to": "Employee Checkin Report",
				"label": "Employee Checkin Report",
				"color": "Purple"
			}
		]
	}
	
	try:
		if frappe.db.exists('Workspace', 'Employee Check-in Dashboard'):
			print("Workspace already exists, updating...")
			doc = frappe.get_doc('Workspace', 'Employee Check-in Dashboard')
			doc.update(workspace_data)
			doc.save(ignore_permissions=True)
		else:
			print("Creating new workspace...")
			doc = frappe.get_doc(workspace_data)
			doc.insert(ignore_permissions=True)
		
		frappe.db.commit()
		print("✓ Workspace installed successfully")
		print("\nAccess it at: /app/employee-check-in-dashboard")
		return "Success"
	except Exception as e:
		print(f"✗ Error: {str(e)}")
		frappe.db.rollback()
		raise


def install_dashboard_charts():
	"""
	Install dashboard charts for Employee Check-in Dashboard
	Run using: bench --site [site] execute hamptons.install_utils.install_dashboard_charts
	"""
	import json
	import os
	
	app_path = frappe.get_app_path('hamptons')
	chart_dir = os.path.join(app_path, 'hamptons', 'dashboard_chart')
	
	charts = [
		'daily_check_ins_overview.json',
		'department_wise_attendance.json',
		'check_in_time_distribution.json'
	]
	
	for chart_file in charts:
		chart_path = os.path.join(chart_dir, chart_file)
		
		if not os.path.exists(chart_path):
			print(f"✗ Chart file not found: {chart_path}")
			continue
			
		with open(chart_path, 'r') as f:
			chart_data = json.load(f)
		
		chart_name = chart_data.get('name') or chart_data.get('chart_name')
		
		try:
			# Check if chart already exists
			if frappe.db.exists('Dashboard Chart', chart_name):
				print(f"Chart '{chart_name}' already exists. Updating...")
				chart = frappe.get_doc('Dashboard Chart', chart_name)
				chart.update(chart_data)
				chart.save(ignore_permissions=True)
			else:
				print(f"Creating chart '{chart_name}'...")
				chart = frappe.get_doc(chart_data)
				chart.insert(ignore_permissions=True)
			
			frappe.db.commit()
			print(f"✓ Chart '{chart_name}' installed successfully")
		except Exception as e:
			print(f"✗ Error installing chart '{chart_name}': {str(e)}")
			frappe.db.rollback()
	
	print("\n✅ Dashboard charts installation complete!")
	print("\nCharts installed:")
	print("1. Daily Check-ins Overview")
	print("2. Department-wise Attendance")
	print("3. Check-in Time Distribution")
	print("\nYou can now add these charts to your Hamptons Workspace")
	return "Charts installed successfully"
