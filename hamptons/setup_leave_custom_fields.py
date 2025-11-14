# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Setup custom fields for Leave Policy compliance
Run using: bench --site [site] execute hamptons.setup_leave_custom_fields.setup_custom_fields
"""

import frappe


def create_custom_field_if_not_exists(doctype, field_dict):
	"""Helper function to create or update a custom field"""
	fieldname = field_dict.get("fieldname")
	try:
		custom_field_name = f"{doctype}-{fieldname}"

		if frappe.db.exists("Custom Field", custom_field_name):
			doc = frappe.get_doc("Custom Field", custom_field_name)
			for key, value in field_dict.items():
				if key != "fieldname":
					setattr(doc, key, value)
		else:
			doc = frappe.new_doc("Custom Field")
			doc.dt = doctype
			for key, value in field_dict.items():
				setattr(doc, key, value)

		doc.save(ignore_permissions=True)
		print(f"  ✓ Created/Updated: {fieldname}")
		return True
	except Exception as e:
		print(f"  ✗ Error creating {fieldname}: {str(e)}")
		frappe.log_error(
			message=f"Error creating custom field {fieldname}: {str(e)}",
			title="Custom Field Creation Error"
		)
		return False


def setup_custom_fields():
	"""
	Create custom fields for Employee doctype to support Oman Leave Policy

	Run using:
	bench --site [site] execute hamptons.setup_leave_custom_fields.setup_custom_fields
	"""
	print("\n" + "="*70)
	print("SETTING UP CUSTOM FIELDS FOR LEAVE POLICY")
	print("="*70 + "\n")

	success_count = 0
	failed_count = 0

	# Employee custom fields
	print("Creating Employee custom fields...")
	print("-" * 70)

	employee_fields = [
		{
			"fieldname": "custom_leave_details_section",
			"label": "Leave Policy Details",
			"fieldtype": "Section Break",
			"insert_after": "attendance_device_id",
			"collapsible": 1
		},
		{
			"fieldname": "custom_nationality",
			"label": "Nationality",
			"fieldtype": "Select",
			"options": "\nOmani\nNon-Omani",
			"insert_after": "custom_leave_details_section",
			"in_standard_filter": 1,
			"description": "Employee nationality for leave policy purposes"
		},
		{
			"fieldname": "custom_religion",
			"label": "Religion",
			"fieldtype": "Select",
			"options": "\nMuslim\nNon-Muslim",
			"insert_after": "custom_nationality",
			"in_standard_filter": 1,
			"description": "Required for Hajj leave and bereavement leave eligibility"
		},
		{
			"fieldname": "custom_hajj_leave_taken",
			"label": "Hajj Leave Taken",
			"fieldtype": "Check",
			"insert_after": "custom_religion",
			"default": 0,
			"description": "Check if employee has already availed Hajj leave (once in service)"
		},
		{
			"fieldname": "custom_hajj_leave_date",
			"label": "Hajj Leave Date",
			"fieldtype": "Date",
			"insert_after": "custom_hajj_leave_taken",
			"depends_on": "eval:doc.custom_hajj_leave_taken==1",
			"description": "Date when Hajj leave was taken"
		},
		{
			"fieldname": "custom_leave_column_break",
			"fieldtype": "Column Break",
			"insert_after": "custom_hajj_leave_date"
		},
		{
			"fieldname": "custom_leave_carryforward_enabled",
			"label": "Enable Leave Carryforward",
			"fieldtype": "Check",
			"insert_after": "custom_leave_column_break",
			"default": 1,
			"description": "Allow employee to carry forward unused annual leaves"
		},
		{
			"fieldname": "custom_max_carryforward_days",
			"label": "Max Carryforward Days",
			"fieldtype": "Int",
			"insert_after": "custom_leave_carryforward_enabled",
			"default": 10,
			"depends_on": "eval:doc.custom_leave_carryforward_enabled==1",
			"description": "Maximum number of days that can be carried forward"
		}
	]

	for field in employee_fields:
		if create_custom_field_if_not_exists("Employee", field):
			success_count += 1
		else:
			failed_count += 1

	print("-" * 70)
	print(f"Employee Fields: {success_count} created/updated, {failed_count} failed\n")

	# Leave Type custom fields
	print("Creating Leave Type custom fields...")
	print("-" * 70)

	leave_type_fields = [
		{
			"fieldname": "custom_oman_leave_section",
			"label": "Oman Labor Law Settings",
			"fieldtype": "Section Break",
			"insert_after": "description",
			"collapsible": 1
		},
		{
			"fieldname": "custom_gender_specific",
			"label": "Gender Specific",
			"fieldtype": "Select",
			"options": "\nAll\nMale\nFemale",
			"insert_after": "custom_oman_leave_section",
			"default": "All",
			"description": "Restrict leave type to specific gender"
		},
		{
			"fieldname": "custom_nationality_specific",
			"label": "Nationality Specific",
			"fieldtype": "Select",
			"options": "\nAll\nOmani\nNon-Omani",
			"insert_after": "custom_gender_specific",
			"default": "All",
			"description": "Restrict leave type to specific nationality"
		},
		{
			"fieldname": "custom_religion_specific",
			"label": "Religion Specific",
			"fieldtype": "Select",
			"options": "\nAll\nAll (Muslim)\nNon-Muslim",
			"insert_after": "custom_nationality_specific",
			"default": "All",
			"description": "Restrict leave type to specific religion (for Hajj leave)"
		},
		{
			"fieldname": "custom_once_in_service",
			"label": "Once in Service",
			"fieldtype": "Check",
			"insert_after": "custom_religion_specific",
			"default": 0,
			"description": "Check if leave can be availed only once during employment (e.g., Hajj Leave)"
		}
	]

	emp_success = success_count
	for field in leave_type_fields:
		if create_custom_field_if_not_exists("Leave Type", field):
			success_count += 1
		else:
			failed_count += 1

	print("-" * 70)
	print(f"Leave Type Fields: {success_count - emp_success} created/updated, {failed_count - (failed_count)} failed\n")

	# Commit all changes
	frappe.db.commit()

	print("="*70)
	print("✅ CUSTOM FIELDS SETUP COMPLETE!")
	print(f"\nTotal: {success_count} created/updated, {failed_count} failed")
	print("\nCustom Fields Summary:")
	print("  Employee: Nationality, Religion, Hajj Tracking, Carryforward")
	print("  Leave Type: Gender/Nationality/Religion restrictions")
	print("="*70 + "\n")

	return {"status": "success", "created": success_count, "failed": failed_count}


def update_leave_types_with_restrictions():
	"""
	Update existing leave types with gender/nationality/religion restrictions

	Run using:
	bench --site [site] execute hamptons.setup_leave_custom_fields.update_leave_types_with_restrictions
	"""
	print("\n" + "="*70)
	print("UPDATING LEAVE TYPES WITH RESTRICTIONS")
	print("="*70 + "\n")

	# Leave Type specific restrictions
	leave_type_restrictions = {
		"Paternity Leave": {
			"custom_gender_specific": "Male",
		},
		"Maternity Leave": {
			"custom_gender_specific": "Female",
		},
		"Hajj Leave": {
			"custom_religion_specific": "All (Muslim)",
			"custom_once_in_service": 1
		},
		"Bereavement Leave - Wife (Muslim Female)": {
			"custom_gender_specific": "Female",
			"custom_religion_specific": "All (Muslim)"
		},
		"Bereavement Leave - Wife (Non-Muslim Female)": {
			"custom_gender_specific": "Female",
			"custom_religion_specific": "Non-Muslim"
		}
	}

	updated_count = 0
	failed_count = 0

	for leave_type_name, restrictions in leave_type_restrictions.items():
		try:
			if frappe.db.exists("Leave Type", leave_type_name):
				doc = frappe.get_doc("Leave Type", leave_type_name)

				for key, value in restrictions.items():
					setattr(doc, key, value)

				doc.save(ignore_permissions=True)
				print(f"  ✓ Updated '{leave_type_name}'")
				updated_count += 1
			else:
				print(f"  ✗ Leave Type '{leave_type_name}' not found")
				failed_count += 1
		except Exception as e:
			print(f"  ✗ Error updating '{leave_type_name}': {str(e)}")
			failed_count += 1

	frappe.db.commit()

	print("\n" + "="*70)
	print(f"✅ UPDATE COMPLETE")
	print(f"   Updated: {updated_count}")
	print(f"   Failed: {failed_count}")
	print("="*70 + "\n")

	return {
		"status": "success",
		"updated_count": updated_count,
		"failed_count": failed_count
	}
