#!/usr/bin/env python3
# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Update Employee Religion and Nationality

Usage:
    # Update single employee
    bench --site hrms.hamptons.om execute hamptons.update_employee_religion.update_single --args "['1002', 'Omani', 'Muslim']"

    # Update multiple employees from predefined list
    bench --site hrms.hamptons.om execute hamptons.update_employee_religion.update_from_mapping

    # View current employee data
    bench --site hrms.hamptons.om execute hamptons.update_employee_religion.show_employee_data
"""

import frappe
from frappe import _


# Predefined mapping of employees (update this based on your actual data)
EMPLOYEE_MAPPING = {
    # Format: 'employee_id': {'nationality': 'Omani/Non-Omani', 'religion': 'Muslim/Non-Muslim'}

    # Example Omani Muslims (update with actual data)
    '1001': {'nationality': 'Omani', 'religion': 'Muslim'},
    '1037': {'nationality': 'Omani', 'religion': 'Muslim'},
    '1040': {'nationality': 'Omani', 'religion': 'Muslim'},

    # Example Non-Omani Muslims (update with actual data)
    '1002': {'nationality': 'Non-Omani', 'religion': 'Muslim'},
    '1021': {'nationality': 'Non-Omani', 'religion': 'Muslim'},

    # Add more employees here...
}


def update_single(employee_id, nationality, religion):
    """
    Update religion and nationality for a single employee

    Args:
        employee_id: Employee ID (e.g., '1002')
        nationality: 'Omani' or 'Non-Omani'
        religion: 'Muslim' or 'Non-Muslim'

    Returns:
        Dictionary with result
    """
    # Validate inputs
    if nationality not in ['Omani', 'Non-Omani']:
        frappe.throw(_("Nationality must be 'Omani' or 'Non-Omani'"))

    if religion not in ['Muslim', 'Non-Muslim']:
        frappe.throw(_("Religion must be 'Muslim' or 'Non-Muslim'"))

    if not frappe.db.exists("Employee", employee_id):
        frappe.throw(_("Employee {0} not found").format(employee_id))

    try:
        emp = frappe.get_doc("Employee", employee_id)
        old_nationality = emp.get("custom_nationality")
        old_religion = emp.get("custom_religion")

        emp.custom_nationality = nationality
        emp.custom_religion = religion
        emp.save(ignore_permissions=True)
        frappe.db.commit()

        print(f"\n✅ Updated Employee {employee_id} - {emp.employee_name}")
        print(f"   Nationality: {old_nationality or 'Not set'} → {nationality}")
        print(f"   Religion: {old_religion or 'Not set'} → {religion}\n")

        return {
            "status": "success",
            "employee_id": employee_id,
            "employee_name": emp.employee_name,
            "nationality": nationality,
            "religion": religion
        }

    except Exception as e:
        frappe.log_error(
            message=f"Error updating employee {employee_id}: {str(e)}",
            title="Employee Update Error"
        )
        frappe.throw(_("Error updating employee: {0}").format(str(e)))


def update_from_mapping(custom_mapping=None):
    """
    Update multiple employees from the EMPLOYEE_MAPPING dictionary

    Args:
        custom_mapping: Optional custom mapping dictionary

    Returns:
        Dictionary with results
    """
    mapping = custom_mapping or EMPLOYEE_MAPPING

    print("\n" + "="*80)
    print("UPDATING EMPLOYEE RELIGION AND NATIONALITY")
    print("="*80 + "\n")

    if not mapping:
        print("⚠ No employee mapping provided")
        print("Please update EMPLOYEE_MAPPING in hamptons/update_employee_religion.py")
        return {"status": "failed", "message": "No mapping provided"}

    print(f"Processing {len(mapping)} employees...\n")
    print("-" * 80 + "\n")

    updated = 0
    failed = 0
    errors = []

    for emp_id, data in mapping.items():
        try:
            if not frappe.db.exists("Employee", emp_id):
                print(f"⊘ Skipped {emp_id}: Employee not found")
                failed += 1
                continue

            emp = frappe.get_doc("Employee", emp_id)
            emp.custom_nationality = data['nationality']
            emp.custom_religion = data['religion']
            emp.save(ignore_permissions=True)

            print(f"✓ {emp_id} - {emp.employee_name}")
            print(f"  → {data['nationality']}, {data['religion']}")
            updated += 1

        except Exception as e:
            error_msg = f"{emp_id}: {str(e)}"
            print(f"✗ Failed {error_msg}")
            errors.append(error_msg)
            failed += 1
            frappe.db.rollback()

    frappe.db.commit()

    print("\n" + "="*80)
    print("UPDATE COMPLETE")
    print("="*80)
    print(f"✓ Updated: {updated}")
    print(f"✗ Failed: {failed}")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"  - {error}")

    print("="*80 + "\n")

    return {
        "status": "success" if failed == 0 else "partial",
        "updated": updated,
        "failed": failed,
        "errors": errors
    }


def show_employee_data(status="Active"):
    """
    Display current employee nationality and religion data

    Args:
        status: Employee status filter (default: 'Active')

    Returns:
        List of employees with their data
    """
    print("\n" + "="*80)
    print("CURRENT EMPLOYEE DATA")
    print("="*80 + "\n")

    employees = frappe.get_all(
        "Employee",
        filters={"status": status},
        fields=["name", "employee_name", "gender", "custom_nationality", "custom_religion"],
        order_by="name"
    )

    if not employees:
        print("No employees found")
        return []

    print(f"{'ID':<8} {'Name':<30} {'Gender':<8} {'Nationality':<15} {'Religion':<12}")
    print("-" * 80)

    muslim_count = 0
    non_muslim_count = 0
    not_set_count = 0

    for emp in employees:
        nationality = emp.get("custom_nationality") or "Not set"
        religion = emp.get("custom_religion") or "Not set"

        if religion == "Muslim":
            muslim_count += 1
        elif religion == "Non-Muslim":
            non_muslim_count += 1
        else:
            not_set_count += 1

        print(f"{emp.name:<8} {emp.employee_name:<30} {emp.gender:<8} {nationality:<15} {religion:<12}")

    print("-" * 80)
    print(f"Total: {len(employees)} employees")
    print(f"  Muslim: {muslim_count}")
    print(f"  Non-Muslim: {non_muslim_count}")
    print(f"  Not Set: {not_set_count}")
    print("="*80 + "\n")

    if not_set_count > 0:
        print("⚠ Warning: Some employees don't have religion set")
        print("  They won't be allocated religion-specific leaves (Hajj Leave, etc.)")
        print("\nTo update, use:")
        print("  bench --site [site] execute hamptons.update_employee_religion.update_single --args \"['EMP_ID', 'Nationality', 'Religion']\"")
        print("\nExample:")
        print("  bench --site hrms.hamptons.om execute hamptons.update_employee_religion.update_single --args \"['1002', 'Non-Omani', 'Muslim']\"")
        print("\n")

    return employees


def bulk_update_from_excel(file_path):
    """
    Update employees from an Excel file

    Excel should have columns: employee_id, nationality, religion

    Args:
        file_path: Path to Excel file

    Returns:
        Dictionary with results
    """
    import pandas as pd

    print("\n" + "="*80)
    print("BULK UPDATE FROM EXCEL")
    print("="*80 + "\n")

    try:
        df = pd.read_excel(file_path)

        required_columns = ['employee_id', 'nationality', 'religion']
        missing = [col for col in required_columns if col not in df.columns]

        if missing:
            frappe.throw(_("Missing columns in Excel: {0}").format(", ".join(missing)))

        print(f"Found {len(df)} rows in Excel\n")

        mapping = {}
        for _, row in df.iterrows():
            emp_id = str(row['employee_id']).strip()
            nationality = str(row['nationality']).strip()
            religion = str(row['religion']).strip()

            # Validate values
            if nationality not in ['Omani', 'Non-Omani']:
                print(f"⚠ Skipping {emp_id}: Invalid nationality '{nationality}'")
                continue

            if religion not in ['Muslim', 'Non-Muslim']:
                print(f"⚠ Skipping {emp_id}: Invalid religion '{religion}'")
                continue

            mapping[emp_id] = {
                'nationality': nationality,
                'religion': religion
            }

        return update_from_mapping(mapping)

    except Exception as e:
        frappe.throw(_("Error reading Excel file: {0}").format(str(e)))


def generate_template_excel(output_path="/tmp/employee_religion_template.xlsx"):
    """
    Generate an Excel template for bulk update

    Args:
        output_path: Path where to save the template

    Returns:
        Path to generated file
    """
    import pandas as pd

    # Get all active employees
    employees = frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["name", "employee_name", "gender", "custom_nationality", "custom_religion"],
        order_by="name"
    )

    # Create dataframe
    data = []
    for emp in employees:
        data.append({
            'employee_id': emp.name,
            'employee_name': emp.employee_name,
            'gender': emp.gender,
            'nationality': emp.get('custom_nationality') or '',
            'religion': emp.get('custom_religion') or '',
            'notes': 'Fill nationality (Omani/Non-Omani) and religion (Muslim/Non-Muslim)'
        })

    df = pd.DataFrame(data)

    # Save to Excel
    df.to_excel(output_path, index=False)

    print(f"\n✅ Template generated: {output_path}")
    print(f"   Contains {len(employees)} employees")
    print("\nInstructions:")
    print("1. Open the Excel file")
    print("2. Fill in the 'nationality' and 'religion' columns")
    print("3. Save the file")
    print("4. Run: bench --site [site] execute hamptons.update_employee_religion.bulk_update_from_excel --args \"['/path/to/file.xlsx']\"")
    print("\n")

    return output_path
