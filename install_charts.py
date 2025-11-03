#!/usr/bin/env python3
"""Install dashboard charts for Employee Check-in Dashboard"""

import frappe
import json
import os

def install_charts():
    """Install all dashboard charts"""
    frappe.connect()
    
    chart_dir = "/home/frappe/frappe-bench/apps/hamptons/hamptons/hamptons/dashboard_chart"
    
    charts = [
        "daily_check_ins_overview.json",
        "department_wise_attendance.json",
        "check_in_time_distribution.json"
    ]
    
    for chart_file in charts:
        chart_path = os.path.join(chart_dir, chart_file)
        
        if not os.path.exists(chart_path):
            print(f"Chart file not found: {chart_path}")
            continue
            
        with open(chart_path, 'r') as f:
            chart_data = json.load(f)
        
        chart_name = chart_data.get("name")
        
        # Check if chart already exists
        if frappe.db.exists("Dashboard Chart", chart_name):
            print(f"Chart '{chart_name}' already exists. Updating...")
            chart = frappe.get_doc("Dashboard Chart", chart_name)
            chart.update(chart_data)
            chart.save()
        else:
            print(f"Creating chart '{chart_name}'...")
            chart = frappe.get_doc(chart_data)
            chart.insert()
        
        frappe.db.commit()
        print(f"✓ Chart '{chart_name}' installed successfully")
    
    print("\n✓ All dashboard charts installed successfully!")
    print("\nYou can now add these charts to your Hamptons Workspace:")
    print("1. Daily Check-ins Overview")
    print("2. Department-wise Attendance")
    print("3. Check-in Time Distribution")

if __name__ == "__main__":
    install_charts()
