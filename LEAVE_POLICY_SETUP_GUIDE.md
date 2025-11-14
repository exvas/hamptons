# Oman Labor Law Leave Policy - Setup Guide

This guide explains how to set up and use the Oman Labor Law compliant leave policy system in your Frappe/ERPNext installation.

## Overview

The system includes:
- **13 Leave Types** based on Oman Labor Law requirements
- **Automatic leave allocation** based on employee attributes (gender, nationality, religion)
- **Leave Control Panel** integration for bulk assignment
- **Custom validations** for leave eligibility

---

## Leave Types Master List

| Leave Type | Days | Nationality | Gender | Notes |
|-----------|------|-------------|--------|-------|
| Annual Leave | 30 | All | All | Earned monthly, can be carried forward, encashable |
| Sick Leave | 21 | All | All | Requires medical certificate after 3 days |
| Paternity Leave | 7 | All | Male | For newborn child |
| Marriage Leave | 3 | All | All | One-time |
| Bereavement Leave | 3 | All | All | Immediate family |
| Bereavement Leave - Extended Family | 2 | All | All | Extended family members |
| Bereavement Leave - Child/Wife | 10 | All | All | Loss of child or spouse |
| Hajj Leave | 15 | All | Muslim | Once in service |
| Exam Leave | 15 | All | All | For students |
| Bereavement Leave - Wife (Muslim Female) | 130 | All | Female (Muslim) | Iddah period |
| Bereavement Leave - Wife (Non-Muslim Female) | 14 | All | Female (Non-Muslim) | |
| Compassionate Leave - Family Member | 15 | All | All | Critical illness of family |
| Maternity Leave | 98 | All | Female | 50 days full pay, 48 days unpaid |

---

## Installation Steps

### Step 1: Setup Custom Fields

Run this command to create custom fields for Employee, Leave Type, and Leave Application:

```bash
bench --site [your-site-name] execute hamptons.setup_leave_custom_fields.setup_custom_fields
```

This will add:
- **Employee fields**: Nationality, Religion, Hajj Leave tracking, Probation status
- **Leave Type fields**: Gender/Nationality/Religion restrictions, Certificate requirements
- **Leave Application fields**: Medical certificate attachment, Salary deduction calculation

---

### Step 2: Create Leave Types and Policy

Run this command to create all 13 leave types and the Oman Labor Law Leave Policy:

```bash
bench --site [your-site-name] execute hamptons.setup_oman_leave_policy.setup_leave_types_and_policy
```

This will:
- Create/update all 13 leave types with proper configurations
- Create "Oman Labor Law Leave Policy" with all leave allocations
- Set up earned leave, encashment, and carryforward rules

---

### Step 3: Update Leave Type Restrictions

Run this command to apply gender/nationality/religion restrictions to leave types:

```bash
bench --site [your-site-name] execute hamptons.setup_leave_custom_fields.update_leave_types_with_restrictions
```

This will:
- Restrict Paternity Leave to Male employees
- Restrict Maternity Leave to Female employees
- Restrict Hajj Leave to Muslim employees
- Set up certificate requirements for Sick Leave (required after 3 days)
- Mark Hajj Leave as "once in service"

---

## Usage Instructions

### Assigning Leave Policy to Employees

#### Method 1: Individual Assignment

Use the Python API to assign policy to a single employee:

```bash
bench --site [your-site-name] console
```

Then in the console:

```python
from hamptons.setup_oman_leave_policy import assign_leave_policy_to_employee

# Assign to specific employee
assign_leave_policy_to_employee(
    employee_id="EMP-00001",
    policy_name="Oman Labor Law Leave Policy",
    effective_from="2025-01-01",
    carry_forward=1
)
```

#### Method 2: Bulk Assignment (All Active Employees)

```bash
bench --site [your-site-name] console
```

Then:

```python
from hamptons.setup_oman_leave_policy import bulk_assign_leave_policy

# Assign to all active employees
bulk_assign_leave_policy(
    filters={"status": "Active"},
    policy_name="Oman Labor Law Leave Policy"
)
```

#### Method 3: Bulk Assignment (Filtered)

Assign to specific department or designation:

```python
from hamptons.setup_oman_leave_policy import bulk_assign_leave_policy

# Assign to specific department
bulk_assign_leave_policy(
    filters={"status": "Active", "department": "HR"},
    policy_name="Oman Labor Law Leave Policy"
)

# Assign to specific designation
bulk_assign_leave_policy(
    filters={"status": "Active", "designation": "Manager"},
    policy_name="Oman Labor Law Leave Policy"
)
```

#### Method 4: Using Leave Control Panel (GUI)

1. Go to: **HR > Leave Control Panel**
2. Select: **Leave Allocation Tool**
3. Choose:
   - **Leave Type**: (Select from dropdown)
   - **From Date**: Start date
   - **To Date**: End date
   - **Employees**: Select employees or use filters
4. Click: **Allocate**

---

## Employee Setup Requirements

Before assigning leave policies, ensure each employee has:

### Required Fields (Standard)
- ✅ Employee ID
- ✅ Employee Name
- ✅ Gender (Male/Female)
- ✅ Date of Joining
- ✅ Status (Active)
- ✅ Company

### Custom Fields (Added by setup script)
- ✅ **Nationality**: Omani / Non-Omani
- ✅ **Religion**: Muslim / Non-Muslim
- ✅ **Probation Completed**: Yes/No
- ✅ **Probation End Date**: (if applicable)

### To Update Employee Data:

1. Go to: **HR > Employee**
2. Open employee record
3. Scroll to **"Leave Policy Details"** section
4. Fill in:
   - Nationality
   - Religion
   - Probation status
5. Save

---

## Leave Allocation Logic

The system automatically determines leave eligibility based on:

### Annual Leave (30 days)
- ✅ Available to: All employees
- ⏰ After: 1 year of service
- 📋 Features: Earned monthly (2.5 days/month), carry forward, encashable

### Sick Leave (21 days)
- ✅ Available to: All employees
- ⏰ After: Probation period (90 days)
- 📋 Features: 15 days full pay, 6 days half pay
- 📄 Requires: Medical certificate after 3 days

### Maternity Leave (98 days)
- ✅ Available to: Female employees only
- ⏰ After: 1 year of service
- 📋 Features: 50 days full pay, 48 days unpaid

### Paternity Leave (7 days)
- ✅ Available to: Male employees only
- ⏰ After: Birth of child
- 📋 Features: Fully paid

### Hajj Leave (15 days)
- ✅ Available to: Muslim employees only
- ⏰ After: 1 year of service
- 📋 Features: Once in service, fully paid

### Bereavement Leave (3-130 days)
- ✅ Available to: All employees (varies by relationship and religion)
- ⏰ After: Immediate
- 📋 Features: Different durations based on:
  - Immediate family: 3 days
  - Extended family: 2 days
  - Child/Wife: 10 days
  - Spouse (Muslim female): 130 days (Iddah period)
  - Spouse (Non-Muslim female): 14 days

---

## Leave Application Process

### For Employees:

1. Go to: **HR > Leave Application**
2. Click: **New**
3. Fill in:
   - **Leave Type**: Select from available types
   - **From Date**: Start date
   - **To Date**: End date
   - **Reason**: Description
   - **Attachments**: Medical certificate (if sick leave > 3 days)
4. Click: **Save** and **Submit**

### System Validations:

The system will automatically:
- ✅ Check leave balance
- ✅ Verify eligibility (gender, nationality, religion)
- ✅ Check certificate requirements
- ✅ Calculate salary deductions (if leaves exhausted)
- ✅ Validate probation status
- ✅ Check "once in service" restrictions (Hajj)

---

## Reports and Monitoring

### Available Reports:

1. **Leave Balance Report**
   - Path: HR > Reports > Leave Balance Report
   - Shows: Current leave balances per employee

2. **Leave Application Report**
   - Path: HR > Reports > Leave Application Report
   - Shows: All leave applications with status

3. **Employee Leave Balance**
   - Path: HR > Reports > Employee Leave Balance
   - Shows: Detailed leave balance by leave type

4. **Leave Ledger Entry**
   - Path: HR > Reports > Leave Ledger Entry
   - Shows: All leave transactions (allocation, application, expiry)

---

## Advanced Configuration

### Customizing Leave Carryforward

Edit the leave policy assignment:

```python
# Set custom carryforward days for specific employee
employee = frappe.get_doc("Employee", "EMP-00001")
employee.custom_max_carryforward_days = 15  # Override default 10 days
employee.save()
```

### Disabling Hajj Leave After Usage

Automatically handled by system - when Hajj Leave is approved:

```python
# This happens automatically on leave approval
employee = frappe.get_doc("Employee", employee_id)
employee.custom_hajj_leave_taken = 1
employee.custom_hajj_leave_date = leave_from_date
employee.save()
```

---

## Troubleshooting

### Issue: Leave policy not applying to employee

**Solution:**
1. Check employee status is "Active"
2. Verify employee has Date of Joining
3. Check Leave Policy Assignment exists and is submitted
4. Clear cache: `bench --site [site] clear-cache`

### Issue: Leave type not showing for employee

**Solution:**
1. Check employee gender matches leave type restriction
2. Verify nationality/religion settings
3. Check if employee has completed probation (for sick leave)
4. Verify leave policy includes that leave type

### Issue: Leave balance showing incorrect

**Solution:**
1. Check Leave Ledger Entry for that employee
2. Verify allocation dates
3. Check for expired leaves
4. Run: `bench --site [site] execute frappe.desk.doctype.leave_allocation.leave_allocation.allocate_leave`

---

## API Reference

### Main Functions

```python
from hamptons.setup_oman_leave_policy import (
    setup_leave_types_and_policy,
    assign_leave_policy_to_employee,
    bulk_assign_leave_policy
)

# Setup entire system
result = setup_leave_types_and_policy()

# Assign to single employee
doc = assign_leave_policy_to_employee("EMP-00001")

# Bulk assign
result = bulk_assign_leave_policy(filters={"status": "Active"})
```

### Custom Field Functions

```python
from hamptons.setup_leave_custom_fields import (
    setup_custom_fields,
    update_leave_types_with_restrictions
)

# Create custom fields
setup_custom_fields()

# Apply restrictions
update_leave_types_with_restrictions()
```

---

## Compliance Checklist

- ✅ Annual Leave: 30 days per year (Oman Labor Law Article 72)
- ✅ Sick Leave: 21 days per year (Oman Labor Law Article 76)
- ✅ Maternity Leave: 98 days (Oman Labor Law Article 82)
- ✅ Paternity Leave: 7 days (Oman Labor Law)
- ✅ Hajj Leave: 15 days once in service (Oman Labor Law Article 73)
- ✅ Bereavement Leave: As per Oman Labor Law Article 75
- ✅ Leave encashment on termination (Oman Labor Law Article 74)
- ✅ Leave carryforward rules

---

## Support

For issues or questions:
1. Check error logs: `bench --site [site] show-error-log`
2. Review frappe logs: `tail -f ~/frappe-bench/logs/[site].log`
3. Contact: Your System Administrator

---

## Changelog

### Version 1.0 (2025-11-14)
- Initial setup with 13 leave types
- Oman Labor Law compliance
- Custom fields for nationality, religion, gender tracking
- Bulk assignment functionality
- Certificate requirement validation
- Once-in-service tracking for Hajj leave

---

**Last Updated**: 2025-11-14
**Compatible with**: ERPNext v15, Frappe v15
