# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime, getdate


def get_data():
	"""
	Get check-in time distribution for today
	Returns data for bar chart showing check-ins by hour
	"""
	today = getdate()
	
	# Query to get check-ins grouped by hour for today
	checkins = frappe.db.sql("""
		SELECT 
			HOUR(time) as hour,
			COUNT(*) as count,
			log_type
		FROM `tabEmployee Checkin`
		WHERE DATE(time) = %s
		GROUP BY HOUR(time), log_type
		ORDER BY hour, log_type
	""", (today,), as_dict=1)
	
	# Prepare data structure for chart
	hours = list(range(24))
	in_counts = {h: 0 for h in hours}
	out_counts = {h: 0 for h in hours}
	
	for checkin in checkins:
		hour = checkin.get('hour')
		count = checkin.get('count', 0)
		log_type = checkin.get('log_type')
		
		if log_type == 'IN':
			in_counts[hour] = count
		else:
			out_counts[hour] = count
	
	# Format labels for working hours (6 AM to 10 PM)
	labels = [f"{h:02d}:00" for h in range(6, 23)]
	in_data = [in_counts[h] for h in range(6, 23)]
	out_data = [out_counts[h] for h in range(6, 23)]
	
	return {
		"labels": labels,
		"datasets": [
			{
				"name": "Check-in",
				"values": in_data
			},
			{
				"name": "Check-out",
				"values": out_data
			}
		],
		"colors": ["#29CD42", "#FF5858"]
	}
