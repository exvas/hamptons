# How to Set Employee Religion and Nationality

## Overview

The Leave Allocation system requires **Religion** and **Nationality** fields to properly allocate religion-specific and nationality-specific leaves according to Oman Labor Law.

## Custom Fields Created

The following custom fields were added to the Employee DocType:

| Field Name | Field Label | Field Type | Options |
|------------|-------------|------------|---------|
| `custom_nationality` | Nationality | Select | Omani, Non-Omani |
| `custom_religion` | Religion | Select | Muslim, Non-Muslim |
| `custom_hajj_leave_taken` | Hajj Leave Taken | Check | - |
| `custom_hajj_leave_date` | Hajj Leave Date | Date | - |

## Method 1: Update via Employee Form (Manual - One Employee)

### Steps:
1. Go to: **HR** → **Employee** → Select employee
2. Scroll down to **Leave Policy Details** section
3. Set the following fields:
   - **Nationality**: Select `Omani` or `Non-Omani`
   - **Religion**: Select `Muslim` or `Non-Muslim`
4. Click **Save**

### Screenshot Location:
```
Employee Form → Leave Policy Details Section
├── Nationality (Dropdown)
└── Religion (Dropdown)
```

## Method 2: Bulk Update via Database (Recommended for Multiple Employees)

### Update All Omani Muslims:
```sql
UPDATE `tabEmployee`
SET custom_nationality = 'Omani',
    custom_religion = 'Muslim'
WHERE name IN ('1001', '1003', '1037', '1040');
```

### Update All Non-Omani Muslims:
```sql
UPDATE `tabEmployee`
SET custom_nationality = 'Non-Omani',
    custom_religion = 'Muslim'
WHERE name IN ('1002', '1021', '1028');
```

### Update Non-Muslims:
```sql
UPDATE `tabEmployee`
SET custom_nationality = 'Non-Omani',
    custom_religion = 'Non-Muslim'
WHERE name IN ('1050', '1051');
```

### Run SQL Commands:
```bash
cd /home/frappe/frappe-bench
bench --site hrms.hamptons.om mariadb
```

Then paste the SQL commands above.

## Method 3: Bulk Update via Python Script (Best for Large Datasets)

Create a file: `/tmp/update_employee_religion.py`

```python
import frappe

def update_employee_religion():
    """Update employee nationality and religion in bulk"""

    # Define employee religion and nationality mapping
    employee_data = {
        # Omani Muslims
        '1001': {'nationality': 'Omani', 'religion': 'Muslim'},
        '1003': {'nationality': 'Omani', 'religion': 'Muslim'},
        '1004': {'nationality': 'Omani', 'religion': 'Muslim'},
        '1005': {'nationality': 'Omani', 'religion': 'Muslim'},

        # Non-Omani Muslims
        '1002': {'nationality': 'Non-Omani', 'religion': 'Muslim'},
        '1021': {'nationality': 'Non-Omani', 'religion': 'Muslim'},

        # Non-Muslims
        '1050': {'nationality': 'Non-Omani', 'religion': 'Non-Muslim'},
    }

    print("\\n" + "="*80)
    print("UPDATING EMPLOYEE RELIGION AND NATIONALITY")
    print("="*80 + "\\n")

    updated = 0
    failed = 0

    for emp_id, data in employee_data.items():
        try:
            emp = frappe.get_doc("Employee", emp_id)
            emp.custom_nationality = data['nationality']
            emp.custom_religion = data['religion']
            emp.save(ignore_permissions=True)
            print(f"✓ Updated {emp_id} - {emp.employee_name}: {data['nationality']}, {data['religion']}")
            updated += 1
        except Exception as e:
            print(f"✗ Failed {emp_id}: {str(e)}")
            failed += 1

    frappe.db.commit()

    print("\\n" + "="*80)
    print(f"Updated: {updated} | Failed: {failed}")
    print("="*80 + "\\n")
```

Run it:
```bash
cd /home/frappe/frappe-bench
bench --site hrms.hamptons.om execute /tmp/update_employee_religion.update_employee_religion
```

## Method 4: Export, Update, Import (Excel-based)

### Step 1: Export Employee Data
```bash
cd /home/frappe/frappe-bench
bench --site hrms.hamptons.om execute frappe.desk.reportview.export_query --args '[["Employee", "name,employee_name,custom_nationality,custom_religion"]]'
```

Or via UI:
1. Go to: **HR** → **Employee** → **List View**
2. Click **Menu** → **Export**
3. Select fields: Employee ID, Employee Name, Nationality, Religion
4. Download Excel

### Step 2: Update Excel
Fill in the **Nationality** and **Religion** columns:
- Nationality: `Omani` or `Non-Omani`
- Religion: `Muslim` or `Non-Muslim`

### Step 3: Import Back
1. Go to: **HR** → **Employee** → **Menu** → **Import**
2. Upload the updated Excel file
3. Map columns
4. Click **Import**

## Verification

### Check Updated Employees:
```bash
cd /home/frappe/frappe-bench
bench --site hrms.hamptons.om mariadb -e "
SELECT
    name as employee_id,
    employee_name,
    gender,
    custom_nationality as nationality,
    custom_religion as religion
FROM \`tabEmployee\`
WHERE status = 'Active'
ORDER BY name
LIMIT 20;
"
```

### Count by Religion:
```sql
SELECT
    custom_religion as religion,
    COUNT(*) as count
FROM \`tabEmployee\`
WHERE status = 'Active'
GROUP BY custom_religion;
```

## Impact on Leave Allocation

Once employee religion and nationality are set:

### Hajj Leave Eligibility
- **Eligible**: Employees with `custom_religion = 'Muslim'`
- **Not Eligible**: Employees with `custom_religion = 'Non-Muslim'` or `NULL`

### Bereavement Leave - Wife (Muslim Female)
- **Eligible**: Female employees with `custom_religion = 'Muslim'`
- **Days**: 130 days

### Bereavement Leave - Wife (Non-Muslim Female)
- **Eligible**: Female employees with `custom_religion = 'Non-Muslim'`
- **Days**: 14 days

## Re-allocate Leaves After Updating Religion

After updating employee religion, you need to allocate religion-specific leaves:

### For a Single Employee:
```bash
bench --site hrms.hamptons.om console
```
```python
from hamptons.import_opening_leave_balances import allocate_single_employee

# Allocate all leaves for employee 1002
allocate_single_employee("1002")
```

### For All Employees:
```bash
bench --site hrms.hamptons.om console
```
```python
from hamptons.import_opening_leave_balances import allocate_leaves_with_opening_balance

# Re-allocate for all active employees
allocate_leaves_with_opening_balance(policy_name="HR-LPOL-2025-00002")
```

**Note**: The allocation script will automatically:
- ✅ Allocate Hajj Leave to Muslim employees
- ✅ Skip Hajj Leave for Non-Muslim employees
- ✅ Skip allocations that already exist
- ✅ Validate gender/nationality/religion restrictions

## Example: Update Sample Employees

Let's say you have the following employees and their actual religions:

```python
# /tmp/update_sample_employees.py
import frappe

def update_sample_employees():
    employees = {
        # Omani Muslim employees (common Omani names)
        '1001': {'nationality': 'Omani', 'religion': 'Muslim'},  # Murtada Al Zadjali
        '1037': {'nationality': 'Omani', 'religion': 'Muslim'},  # Nasser Al Balushi
        '1040': {'nationality': 'Omani', 'religion': 'Muslim'},
        '1041': {'nationality': 'Omani', 'religion': 'Muslim'},
        '1032': {'nationality': 'Omani', 'religion': 'Muslim'},

        # Non-Omani Muslim employees (Indian/Pakistani Muslim names)
        '1002': {'nationality': 'Non-Omani', 'religion': 'Muslim'},  # Mohammed Ishtiyaq
        '1021': {'nationality': 'Non-Omani', 'religion': 'Muslim'},  # Faizul Kabeer

        # Add more as needed...
    }

    for emp_id, data in employees.items():
        try:
            if frappe.db.exists("Employee", emp_id):
                emp = frappe.get_doc("Employee", emp_id)
                emp.custom_nationality = data['nationality']
                emp.custom_religion = data['religion']
                emp.save(ignore_permissions=True)
                print(f"✓ {emp_id} - {emp.employee_name}: {data['religion']}")
        except Exception as e:
            print(f"✗ {emp_id}: {str(e)}")

    frappe.db.commit()
    print("\\nDone!")
```

Run it:
```bash
bench --site hrms.hamptons.om execute /tmp/update_sample_employees.update_sample_employees
```

## Common Issues

### Issue 1: Field Not Visible
**Solution**: The custom fields are in the **Leave Policy Details** section. Scroll down on the Employee form to find them.

### Issue 2: Field Shows But Can't Save
**Solution**:
1. Check if custom fields are installed: `bench --site hrms.hamptons.om execute hamptons.setup_leave_custom_fields.setup_custom_fields`
2. Clear cache: `bench --site hrms.hamptons.om clear-cache`

### Issue 3: Bulk Update Not Working
**Solution**: Make sure you're using the exact values:
- Nationality: `Omani` or `Non-Omani` (case-sensitive)
- Religion: `Muslim` or `Non-Muslim` (case-sensitive)

## Validation After Update

After updating employee religion, test the allocation:

```bash
bench --site hrms.hamptons.om execute hamptons.test_policy_assignment_validation.test_leave_policy_assignment_validation
```

This will show:
- ✅ Which leaves are correctly blocked
- ✅ Which leaves are correctly allocated
- ❌ Any validation errors

## Summary

1. **Update employee religion** using one of the methods above
2. **Verify updates** with SQL query
3. **Re-allocate leaves** for affected employees
4. **Test validation** to ensure it works correctly

---

**Need Help?**
- Check custom fields exist: `bench --site hrms.hamptons.om execute hamptons.setup_leave_custom_fields.setup_custom_fields`
- View employee data: `bench --site hrms.hamptons.om mariadb -e "SELECT * FROM \`tabEmployee\` WHERE name = '1002'\\G"`
- Contact system administrator

**Created**: 2025-11-22
**App**: Hamptons v0.0.1
