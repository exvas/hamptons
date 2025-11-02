#!/usr/bin/env python3
"""Script to cancel all submitted Attendance records"""

import frappe

def cancel_all():
	"""Cancel all submitted attendance records"""
	frappe.db.auto_commit_on_many_writes = True
	
	submitted = frappe.get_all('Attendance', filters={'docstatus': 1}, pluck='name')
	total = len(submitted)
	cancelled = 0
	failed = 0
	
	print(f"Found {total} submitted Attendance records...")
	
	for idx, name in enumerate(submitted, 1):
		try:
			doc = frappe.get_doc('Attendance', name)
			doc.cancel()
			cancelled += 1
			if idx % 100 == 0:
				print(f"Progress: {idx}/{total}")
				frappe.db.commit()
		except Exception as e:
			failed += 1
	
	frappe.db.commit()
	print(f"\nDONE: Cancelled={cancelled}, Failed={failed}")
	return {'cancelled': cancelled, 'failed': failed}
