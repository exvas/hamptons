#!/usr/bin/env python3
"""
Test script to verify time-based IN/OUT inference for Attendance Regularization

This script tests the fix for the issue where biometric devices mark all checkins as "IN"
instead of alternating IN/OUT based on time sequence.

Test Case: Employee 1037 (Nasser Al Balushi) on 2025-11-23
Expected: 3 checkins marked as IN, should be inferred as IN-OUT-IN
"""

import frappe
from frappe.utils import getdate
from hamptons.overrides.attendance_utils import infer_log_type_from_sequence, get_first_in_last_out


def test_inference_logic():
	"""Test the inference logic with sample data"""
	print("\n" + "="*80)
	print("TEST 1: Inference Logic with Sample Data")
	print("="*80)

	# Sample checkins (all marked as IN from device)
	sample_checkins = [
		{"time": "2025-11-23 07:14:18", "log_type": "IN", "name": "CHECK1"},
		{"time": "2025-11-23 14:57:45", "log_type": "IN", "name": "CHECK2"},
		{"time": "2025-11-23 17:06:05", "log_type": "IN", "name": "CHECK3"}
	]

	print("\nOriginal checkins (all from device as IN):")
	for c in sample_checkins:
		print(f"  {c['time']} - {c['log_type']} ({c['name']})")

	# Test inference
	inferred = infer_log_type_from_sequence(sample_checkins)

	print("\nInferred checkins:")
	for c in inferred:
		print(f"  {c['time']} - {c['inferred_log_type']} (was: {c['original_log_type']}) ({c['name']})")

	# Test first IN, last OUT
	first_in, last_out = get_first_in_last_out(sample_checkins, use_inferred=True)

	print("\nConsolidated:")
	if first_in:
		print(f"  First IN:  {first_in['time']} ({first_in.get('inferred_log_type', 'N/A')})")
	if last_out:
		print(f"  Last OUT:  {last_out['time']} ({last_out.get('inferred_log_type', 'N/A')})")

	return inferred, first_in, last_out


def test_actual_employee_data():
	"""Test with actual employee 1037 data"""
	print("\n" + "="*80)
	print("TEST 2: Actual Employee Data (Employee 1037 on 2025-11-23)")
	print("="*80)

	frappe.init(site="hrms.hamptons.om")
	frappe.connect()

	# Get all checkins for employee 1037 on 2025-11-23
	checkins = frappe.db.sql("""
		SELECT name, employee, employee_name, time, log_type
		FROM `tabEmployee Checkin`
		WHERE employee = '1037'
		AND DATE(time) = '2025-11-23'
		ORDER BY time ASC
	""", as_dict=True)

	if not checkins:
		print("\n❌ No checkins found for employee 1037 on 2025-11-23")
		return

	print(f"\nFound {len(checkins)} checkins:")
	for c in checkins:
		print(f"  {c.name}: {c.time} - {c.log_type}")

	# Test inference
	inferred = infer_log_type_from_sequence(checkins)

	print("\nInferred log types:")
	for c in inferred:
		original = c.get('original_log_type', c.get('log_type'))
		inferred_type = c.get('inferred_log_type')
		symbol = "✓" if original == inferred_type else "⚠"
		print(f"  {symbol} {c['time']} - {inferred_type} (device said: {original})")

	# Test consolidation
	first_in, last_out = get_first_in_last_out(checkins, use_inferred=True)

	print("\nConsolidated for Attendance:")
	if first_in:
		print(f"  ✓ First IN:  {first_in['time']} ({first_in.get('inferred_log_type')})")
	else:
		print(f"  ❌ First IN:  Not found")

	if last_out:
		print(f"  ✓ Last OUT:  {last_out['time']} ({last_out.get('inferred_log_type')})")
	else:
		print(f"  ❌ Last OUT:  Not found")

	frappe.destroy()


def test_reprocess_regularization():
	"""Test reprocessing the attendance regularization"""
	print("\n" + "="*80)
	print("TEST 3: Reprocess Attendance Regularization AR250510")
	print("="*80)

	frappe.init(site="hrms.hamptons.om")
	frappe.connect()

	# Get the existing regularization
	reg_name = "AR250510"

	try:
		reg = frappe.get_doc("Attendance Regularization", reg_name)
		print(f"\n📋 Existing Regularization: {reg_name}")
		print(f"   Employee: {reg.employee} - {reg.employee_name}")
		print(f"   Date: {reg.posting_date}")
		print(f"   Status: {reg.status}")
		print(f"   Shift: {reg.shift}")
		print(f"   Late: {reg.late}")

		print(f"\n   Current checkin items ({len(reg.attendance_regularization_item)}):")
		for item in reg.attendance_regularization_item:
			print(f"     - {item.time} ({item.log_type}) - Checkin: {item.employee_checkin}")

		# Check if it's in draft
		if reg.docstatus == 0:
			print("\n✓ Regularization is in Draft status - can be updated")

			# Get all checkins for this date
			checkins = frappe.db.sql("""
				SELECT name, time, log_type
				FROM `tabEmployee Checkin`
				WHERE employee = %s
				AND DATE(time) = %s
				ORDER BY time ASC
			""", (reg.employee, reg.posting_date), as_dict=True)

			print(f"\n📊 Processing {len(checkins)} checkins with time-based inference...")

			# Infer and consolidate
			first_in, last_out = get_first_in_last_out(checkins, use_inferred=True)

			print(f"\n   New consolidated checkins:")
			if first_in:
				print(f"     ✓ First IN:  {first_in['time']} ({first_in.get('inferred_log_type')})")
			if last_out:
				print(f"     ✓ Last OUT:  {last_out['time']} ({last_out.get('inferred_log_type')})")

			# Calculate late time
			from hamptons.overrides.attendance_utils import calculate_late_early_times
			shift_type = frappe.get_doc("Shift Type", reg.shift)
			result = calculate_late_early_times(
				first_in["time"] if first_in else None,
				last_out["time"] if last_out else None,
				shift_type,
				getdate(reg.posting_date)
			)

			print(f"\n   Late/Early Calculation:")
			print(f"     Late Time: {result['late_time']}")
			print(f"     Early Exit: {result['early_exit_time']}")
			print(f"     Needs Regularization: {result['needs_regularization']}")

			# Update the regularization
			print(f"\n🔄 Would update regularization with:")
			print(f"     - Clear existing items")
			print(f"     - Add First IN: {first_in['time']} ({first_in.get('inferred_log_type')})")
			print(f"     - Add Last OUT: {last_out['time']} ({last_out.get('inferred_log_type')})")
			print(f"     - Update late time: {result['late_time']}")

		else:
			print(f"\n⚠ Regularization is {['Draft', 'Submitted', 'Cancelled'][reg.docstatus]} - cannot auto-update")

	except frappe.DoesNotExistError:
		print(f"\n❌ Regularization {reg_name} not found")

	frappe.destroy()


if __name__ == "__main__":
	print("\n" + "="*80)
	print("ATTENDANCE REGULARIZATION - TIME-BASED IN/OUT INFERENCE TEST")
	print("="*80)

	# Run tests
	test_inference_logic()
	test_actual_employee_data()
	test_reprocess_regularization()

	print("\n" + "="*80)
	print("✓ All tests completed")
	print("="*80 + "\n")
