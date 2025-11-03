#!/usr/bin/env python3
"""
Install Employee Check-in Dashboard
This script creates the workspace and dashboard charts in the database
"""

import frappe
from frappe import _
import json
import os


def install_dashboard():
	"""Install the Employee Check-in Dashboard workspace and charts"""
	
	frappe.init(site='hrms.hamptons.om')
	frappe.connect()
	
	app_path = frappe.get_app_path('hamptons')
	
	# Install Workspace
	print("Installing Employee Check-in Dashboard Workspace...")
	workspace_path = os.path.join(app_path, 'hamptons', 'workspace', 'employee_checkin_dashboard.json')
	
	try:
		with open(workspace_path, 'r') as f:
			workspace_data = json.load(f)
		
		# Check if workspace already exists
		if frappe.db.exists('Workspace', 'Employee Check-in Dashboard'):
			print("  Workspace already exists, updating...")
			doc = frappe.get_doc('Workspace', 'Employee Check-in Dashboard')
			doc.update(workspace_data)
			doc.save()
		else:
			print("  Creating new workspace...")
			doc = frappe.get_doc(workspace_data)
			doc.insert()
		
		frappe.db.commit()
		print("  ✓ Workspace installed successfully")
	except Exception as e:
		print(f"  ✗ Error installing workspace: {str(e)}")
		frappe.db.rollback()
	
	# Install Dashboard Charts
	chart_files = [
		'daily_check_ins_overview.json',
		'department_wise_attendance.json',
		'check_in_time_distribution.json'
	]
	
	chart_path = os.path.join(app_path, 'hamptons', 'dashboard_chart')
	
	for chart_file in chart_files:
		print(f"Installing chart: {chart_file}...")
		try:
			with open(os.path.join(chart_path, chart_file), 'r') as f:
				chart_data = json.load(f)
			
			chart_name = chart_data.get('name') or chart_data.get('chart_name')
			
			# Check if chart already exists
			if frappe.db.exists('Dashboard Chart', chart_name):
				print(f"  Chart '{chart_name}' already exists, updating...")
				doc = frappe.get_doc('Dashboard Chart', chart_name)
				doc.update(chart_data)
				doc.save()
			else:
				print(f"  Creating new chart '{chart_name}'...")
				doc = frappe.get_doc(chart_data)
				doc.insert()
			
			frappe.db.commit()
			print(f"  ✓ Chart installed successfully")
		except Exception as e:
			print(f"  ✗ Error installing chart: {str(e)}")
			frappe.db.rollback()
	
	# Install Number Cards
	print("Installing Number Cards...")
	if 'number_cards' in workspace_data:
		for card in workspace_data['number_cards']:
			try:
				card_name = card.get('name')
				if frappe.db.exists('Number Card', card_name):
					print(f"  Number Card '{card_name}' already exists, skipping...")
				else:
					print(f"  Creating Number Card '{card_name}'...")
					card_doc = frappe.get_doc({
						'doctype': 'Number Card',
						**card
					})
					card_doc.insert()
					frappe.db.commit()
					print(f"  ✓ Number Card installed")
			except Exception as e:
				print(f"  ✗ Error installing number card: {str(e)}")
				frappe.db.rollback()
	
	print("\n✅ Dashboard installation complete!")
	print("Access it at: http://hrms.hamptons.om/app/employee-check-in-dashboard")
	
	frappe.destroy()


if __name__ == '__main__':
	install_dashboard()
