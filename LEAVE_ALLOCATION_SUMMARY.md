# Leave Allocation Summary - November 2025

## ✅ Allocation Complete!

**Date**: 2025-11-14
**Site**: hrms.hamptons.om
**Policy**: HR-LPOL-2025-00002 (Oman Labor Law Leave Policy)

---

## 📊 Allocation Statistics

| Metric | Count |
|--------|-------|
| **Total Employees Processed** | 56 |
| **Leave Allocations Created** | 339 |
| **Allocation Period** | 2025-11-14 to 2026-11-14 |
| **Status** | ✅ Successfully Submitted |

---

## 📋 Leave Types Allocated

Each eligible employee received allocations for the following leave types:

| Leave Type | Standard Allocation | Notes |
|-----------|---------------------|-------|
| **Annual Leave** | Opening Balance (varies) | Used actual balances from November 2025 data |
| **Sick Leave** | 21 days | All employees |
| **Paternity Leave** | 7 days | Male employees only |
| **Maternity Leave** | 98 days | Female employees only |
| **Marriage Leave** | 3 days | All employees |
| **Bereavement Leave** | 3 days | All employees |
| **Bereavement Leave - Extended Family** | 2 days | All employees |
| **Bereavement Leave - Child/Wife** | 10 days | All employees |
| **Hajj Leave** | 15 days | Skipped (Religion not set) |
| **Exam Leave** | 15 days | All employees |
| **Compassionate Leave - Family Member** | 15 days | All employees |
| **Bereavement Leave - Wife (Muslim Female)** | 130 days | Skipped (Gender/Religion) |
| **Bereavement Leave - Wife (Non-Muslim Female)** | 14 days | Skipped (Gender/Religion) |

---

## 🔍 Sample Employee Allocations

### Employee: 1021 (Faizul Kabeer)
**Opening Annual Leave Balance**: 3 days

| Leave Type | Allocated |
|-----------|-----------|
| Annual Leave | 3 days |
| Sick Leave | 21 days |
| Paternity Leave | 7 days |
| Marriage Leave | 3 days |
| Bereavement Leave | 3 days |
| Bereavement Leave - Extended Family | 2 days |
| Bereavement Leave - Child/Wife | 10 days |
| Exam Leave | 15 days |
| Compassionate Leave - Family Member | 15 days |
| **Total** | **79 days** |

### Employee: 1037 (Nasser Al Balushi)
**Opening Annual Leave Balance**: 16 days

| Leave Type | Allocated |
|-----------|-----------|
| Annual Leave | 16 days |
| Sick Leave | 21 days |
| Paternity Leave | 7 days |
| Marriage Leave | 3 days |
| Bereavement Leave | 3 days |
| Bereavement Leave - Extended Family | 2 days |
| Bereavement Leave - Child/Wife | 10 days |
| Exam Leave | 15 days |
| Compassionate Leave - Family Member | 15 days |
| **Total** | **92 days** |

### Employee: 1001 (Murtada Al Zadjali)
**Opening Annual Leave Balance**: 30 days

| Leave Type | Allocated |
|-----------|-----------|
| Annual Leave | 30 days |
| Sick Leave | 21 days |
| Paternity Leave | 7 days |
| Marriage Leave | 3 days |
| Bereavement Leave | 3 days |
| Bereavement Leave - Extended Family | 2 days |
| Bereavement Leave - Child/Wife | 10 days |
| Exam Leave | 15 days |
| Compassionate Leave - Family Member | 15 days |
| **Total** | **106 days** |

---

## ⚠️ Important Notes

### 1. **Gender/Religion Restrictions**
Some leave types were automatically skipped based on employee attributes:
- **Hajj Leave** - Requires Religion = "Muslim" (currently not set for employees)
- **Maternity Leave** - Only for Female employees
- **Paternity Leave** - Only for Male employees
- **Bereavement Leave (Wife)** - Gender and religion specific

**Action Required**: Update employee records with:
- Nationality (Omani/Non-Omani)
- Religion (Muslim/Non-Muslim)

Once updated, re-run allocation for Hajj Leave:
```bash
cd /home/frappe/frappe-bench
bench --site hrms.hamptons.om console
```
```python
from hamptons.import_opening_leave_balances import allocate_single_employee
allocate_single_employee("1021")  # Replace with employee ID
```

### 2. **Zero/Negative Balances Skipped**
Employees with 0 or negative Annual Leave balances did not receive Annual Leave allocation:
- Employee 1004: 0 days
- Employee 1026: -1 day
- Employee 1044: -1 day
- Others with 0 balance

These employees still received all other leave types (Sick, Paternity, etc.)

### 3. **Carry Forward**
Only **Annual Leave** has carry forward enabled. All other leaves expire at the end of the allocation period.

---

## 📅 Allocation Period

- **From Date**: 2025-11-14
- **To Date**: 2026-11-14
- **Duration**: 1 year

**Annual Leave accrual**: 2.5 days per month for new allocations

---

## 🔄 How to View Leave Balances

### Method 1: Employee-wise (GUI)
1. Go to: **HR** → **Leave Allocation**
2. Filter by Employee
3. View all allocated leave types

### Method 2: Report
1. Go to: **HR** → **Reports** → **Leave Balance Report**
2. Select date range
3. Export to Excel if needed

### Method 3: Query (Quick Check)
```bash
cd /home/frappe/frappe-bench
bench --site hrms.hamptons.om mariadb
```
```sql
SELECT
    employee,
    employee_name,
    leave_type,
    new_leaves_allocated,
    from_date,
    to_date
FROM `tabLeave Allocation`
WHERE docstatus = 1
    AND employee = '1021'
ORDER BY leave_type;
```

---

## 📝 Next Steps

### 1. **Update Employee Data** (Recommended)
Go to each employee record and fill in:
- **Nationality**: Omani / Non-Omani
- **Religion**: Muslim / Non-Muslim

Path: **HR** → **Employee** → [Select Employee] → **Leave Policy Details** section

### 2. **Re-allocate Hajj Leave** (After updating religion)
For Muslim employees who should get Hajj Leave:
```python
from hamptons.import_opening_leave_balances import allocate_single_employee

# Run for each Muslim employee
allocate_single_employee("1021")
```

### 3. **Train Employees on Leave Application**
Employees can now apply for leaves:
1. Login to ERPNext
2. Go to: **HR** → **Leave Application** → **New**
3. Select leave type
4. Choose dates
5. Submit for approval

### 4. **Setup Leave Approval Workflow** (Optional)
Configure who can approve leaves:
1. Go to: **HR** → **Leave Application** → **Workflow**
2. Set up approval hierarchy
3. Configure email notifications

---

## 🐛 Troubleshooting

### Issue: Employee can't see leave types
**Solution**: Check Leave Allocation exists and is submitted (docstatus=1)

### Issue: Leave balance showing wrong
**Solution**:
1. Check Leave Ledger Entry: **HR** → **Reports** → **Leave Ledger Entry**
2. Verify no duplicate allocations exist
3. Clear cache: `bench --site hrms.hamptons.om clear-cache`

### Issue: Need to update allocation
**Solution**: Cancel existing allocation and create new one
```python
# In bench console
allocation = frappe.get_doc("Leave Allocation", "HR-LAL-2025-XXXXX")
allocation.cancel()
frappe.db.commit()

# Then re-run allocation script
```

---

## 📞 Support

For questions or issues:
1. Check error logs: `bench --site hrms.hamptons.om show-error-log`
2. Review frappe logs: `tail -f ~/frappe-bench/logs/hrms.hamptons.om.log`
3. Contact System Administrator

---

## 📂 Related Files

- **Setup Script**: `/home/frappe/frappe-bench/apps/hamptons/hamptons/import_opening_leave_balances.py`
- **Leave Policy Setup**: `/home/frappe/frappe-bench/apps/hamptons/hamptons/setup_oman_leave_policy.py`
- **Custom Fields**: `/home/frappe/frappe-bench/apps/hamptons/hamptons/setup_leave_custom_fields.py`
- **User Guide**: `/home/frappe/frappe-bench/apps/hamptons/LEAVE_POLICY_SETUP_GUIDE.md`

---

**Allocation completed successfully on**: 2025-11-14
**System**: ERPNext v15 | Frappe v15
**App**: Hamptons v0.0.1
