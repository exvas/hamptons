# Flexible Hajj Leave Policy - Implementation

## Date: November 22, 2025

---

## Overview

The Hajj Leave system now implements a **flexible once-in-service** policy that allows re-allocation if the previous allocation was not consumed.

---

## Policy Rules

### Once-in-Service with Flexibility

**Traditional (Strict):**
- Hajj Leave allocated once → Cannot allocate again, even if unused

**New (Flexible):**
- Hajj Leave allocated → Employee can apply for leave
- If **consumed** (Leave Application approved and taken) → Cannot re-allocate
- If **NOT consumed** (allocation expired unused) → Can re-allocate in future years

---

## How It Works

### Scenario 1: First Time Allocation

**Action:** HR allocates Hajj Leave to Employee 1002 for 2025
```
✅ Hajj Leave allocation created (valid: 01-01-2025 to 31-12-2025)
✅ Employee can apply for Hajj Leave
❌ custom_hajj_leave_taken = 0 (not yet consumed)
```

### Scenario 2: Employee Uses Hajj Leave

**Action:** Employee 1002 applies for Hajj Leave (01-06-2025 to 16-06-2025)
```
✅ Leave Application submitted and approved
✅ On approval: custom_hajj_leave_taken = 1
✅ custom_hajj_leave_date = 01-06-2025
❌ Cannot re-allocate Hajj Leave in future (consumed)
```

### Scenario 3: Employee Doesn't Use Hajj Leave (2025)

**Action:** Employee 1002 doesn't apply for Hajj Leave in 2025
```
⏰ Allocation expires on 31-12-2025
❌ custom_hajj_leave_taken = 0 (never consumed)
✅ Can allocate again in 2026 or later
```

**Action:** HR allocates Hajj Leave again in 2026
```
✅ NEW Hajj Leave allocation created (valid: 01-01-2026 to 31-12-2026)
✅ Employee can apply for Hajj Leave in 2026
```

### Scenario 4: Employee Cancels Hajj Leave (Before Start Date)

**Action:** Employee applies for Hajj Leave, then cancels **before** leave starts
```
✅ Leave Application approved (custom_hajj_leave_taken = 1)
✅ Employee cancels Leave Application before 01-06-2025
✅ System automatically resets: custom_hajj_leave_taken = 0
✅ Can apply for Hajj Leave again in same year or re-allocate next year
```

---

## System Behavior

### When Allocating Hajj Leave (Leave Control Panel)

The system checks:

1. **Is Hajj Leave consumed?**
   - Query: Are there any **approved** Leave Applications for Hajj Leave?
   - If **YES** → ❌ Skip allocation ("Hajj Leave already consumed from X to Y")
   - If **NO** → Continue to step 2

2. **Is there an active allocation?**
   - Query: Is there a **non-expired** Hajj Leave allocation?
   - If **YES** → ❌ Skip allocation ("Hajj Leave allocation already active until X")
   - If **NO** → ✅ Allow allocation

3. **Result:**
   - ✅ Valid allocations created
   - ⚠️ Invalid allocations skipped silently
   - 📝 Skipped leaves logged

### When Applying for Hajj Leave (Leave Application)

The employee submits a Leave Application:

1. Employee creates Leave Application for Hajj Leave
2. Leave Application is submitted and approved
3. **on_submit hook triggers:**
   - Sets `custom_hajj_leave_taken = 1`
   - Sets `custom_hajj_leave_date = from_date`
   - Hajj Leave is now marked as **consumed**

### When Cancelling Hajj Leave (Before Start Date)

If employee cancels Leave Application **before** the leave starts:

1. Employee cancels Leave Application
2. **on_cancel hook triggers:**
   - Checks if `from_date > today` (leave hasn't started)
   - Checks if there are other approved Hajj Leave applications
   - If no other approved applications:
     - Resets `custom_hajj_leave_taken = 0`
     - Resets `custom_hajj_leave_date = NULL`
   - Hajj Leave is now **available again**

---

## Database Fields

### Employee DocType

| Field | Type | Purpose |
|-------|------|---------|
| `custom_hajj_leave_taken` | Check | 1 = Consumed, 0 = Not consumed |
| `custom_hajj_leave_date` | Date | Date when Hajj Leave was **consumed** (Leave Application approved) |

**Important:** These fields are set when Leave Application is **approved**, NOT when allocation is created.

---

## Examples

### Example 1: Normal Flow - Employee Takes Hajj in 2025

```
2025:
  HR allocates Hajj Leave (01-01-2025 to 31-12-2025)
  Employee applies for Hajj Leave (01-06-2025 to 16-06-2025)
  Leave approved → custom_hajj_leave_taken = 1

2026:
  HR tries to allocate Hajj Leave
  ❌ System blocks: "Hajj Leave already consumed (from 01-06-2025 to 16-06-2025)"
```

### Example 2: Employee Doesn't Go for Hajj in 2025, Goes in 2026

```
2025:
  HR allocates Hajj Leave (01-01-2025 to 31-12-2025)
  Employee doesn't apply
  Allocation expires → custom_hajj_leave_taken = 0

2026:
  HR allocates Hajj Leave again (01-01-2026 to 31-12-2026)
  ✅ System allows: "No consumed leave found, no active allocation"
  Employee applies for Hajj Leave (15-06-2026 to 30-06-2026)
  Leave approved → custom_hajj_leave_taken = 1

2027:
  ❌ Cannot allocate again (consumed in 2026)
```

### Example 3: Employee Gets Hajj Allocated, Then Visa Rejected

```
2025:
  HR allocates Hajj Leave (01-01-2025 to 31-12-2025)
  Employee applies for Hajj Leave (01-06-2025 to 16-06-2025)
  Leave approved → custom_hajj_leave_taken = 1
  Employee's visa gets rejected → Cancels Leave Application (before 01-06-2025)
  System resets → custom_hajj_leave_taken = 0

2026:
  HR allocates Hajj Leave again (01-01-2026 to 31-12-2026)
  ✅ System allows: "No consumed leave, previous application was cancelled"
```

### Example 4: Duplicate Allocation Prevention

```
2025:
  HR allocates Hajj Leave (01-01-2025 to 31-12-2025)
  HR tries to allocate again in same year
  ❌ System blocks: "Hajj Leave allocation already active (valid until 31-12-2025)"
```

---

## Technical Implementation

### Files Modified

1. **[leave_control_panel.py](file:///home/frappe/frappe-bench/apps/hamptons/hamptons/overrides/leave_control_panel.py)**
   - `check_leave_eligibility()` - Checks if Hajj Leave was consumed
   - Updated logic to check Leave Applications, not just allocations

2. **[leave_allocation.py](file:///home/frappe/frappe-bench/apps/hamptons/hamptons/overrides/leave_allocation.py)**
   - Updated Hajj Leave validation to check consumed status
   - Removed automatic flag setting on allocation submission

3. **[leave_application.py](file:///home/frappe/frappe-bench/apps/hamptons/hamptons/overrides/leave_application.py)** ⭐ NEW
   - `on_submit_leave_application()` - Marks Hajj Leave as consumed when approved
   - `on_cancel_leave_application()` - Unmarks if cancelled before start date

4. **[hooks.py](file:///home/frappe/frappe-bench/apps/hamptons/hamptons/hooks.py)**
   - Added Leave Application hooks for on_submit and on_cancel

### Validation Logic

```python
def check_leave_eligibility(employee_id, leave_type_name):
    if leave_type_name == "Hajj Leave":
        # 1. Check if consumed (Leave Application approved)
        consumed_leave = frappe.db.sql("""
            SELECT name, from_date, to_date
            FROM `tabLeave Application`
            WHERE employee = %s
                AND leave_type = 'Hajj Leave'
                AND docstatus = 1
                AND status IN ('Approved', 'Open')
        """, (employee_id,))

        if consumed_leave:
            return False, "Already consumed"

        # 2. Check if active allocation exists
        active_allocation = frappe.db.sql("""
            SELECT name, to_date
            FROM `tabLeave Allocation`
            WHERE employee = %s
                AND leave_type = 'Hajj Leave'
                AND docstatus = 1
                AND to_date >= today()
        """, (employee_id,))

        if active_allocation:
            return False, "Active allocation exists"

        # 3. Allow allocation
        return True, None
```

---

## User Instructions

### For HR Team

#### Allocating Hajj Leave

1. Go to: **HR** → **Leave Control Panel**
2. Select employees and Leave Policy
3. Click "Allocate Leave"
4. System will:
   - ✅ Allocate Hajj Leave if eligible
   - ⚠️ Skip if already consumed or active allocation exists
   - 📝 Log skipped allocations

#### Checking Hajj Leave Status

**Via Employee Form:**
1. Open Employee record
2. Go to "Leave Policy Details" section
3. Check:
   - **Hajj Leave Taken** checkbox (1 = consumed, 0 = not consumed)
   - **Hajj Leave Date** (date when consumed)

**Via Leave Allocation List:**
```sql
SELECT name, from_date, to_date, new_leaves_allocated
FROM `tabLeave Allocation`
WHERE employee = '1002'
  AND leave_type = 'Hajj Leave'
  AND docstatus = 1
ORDER BY from_date DESC;
```

**Via Leave Application List:**
```sql
SELECT name, from_date, to_date, status
FROM `tabLeave Application`
WHERE employee = '1002'
  AND leave_type = 'Hajj Leave'
  AND docstatus = 1
ORDER BY from_date DESC;
```

### For Employees

#### Applying for Hajj Leave

1. Ensure you have Hajj Leave **allocated** (check Leave Balance)
2. Go to: **HR** → **Leave Application** → **New**
3. Select:
   - Leave Type: Hajj Leave
   - From Date & To Date
4. Submit application
5. Wait for approval

#### If Plans Change (Visa Rejection, etc.)

1. **Before leave starts:** Cancel Leave Application
   - System will reset your Hajj Leave status
   - You can apply again in future

2. **After leave starts:** Cannot cancel
   - Hajj Leave is considered consumed
   - Cannot get Hajj Leave again during service

---

## Monitoring

### Check Consumed vs Allocated Hajj Leaves

```sql
SELECT
    e.name as employee_id,
    e.employee_name,
    e.custom_hajj_leave_taken,
    e.custom_hajj_leave_date,
    (SELECT COUNT(*)
     FROM `tabLeave Allocation`
     WHERE employee = e.name
       AND leave_type = 'Hajj Leave'
       AND docstatus = 1) as allocation_count,
    (SELECT COUNT(*)
     FROM `tabLeave Application`
     WHERE employee = e.name
       AND leave_type = 'Hajj Leave'
       AND docstatus = 1
       AND status IN ('Approved', 'Open')) as consumed_count
FROM `tabEmployee` e
WHERE e.custom_religion = 'Muslim'
  AND e.status = 'Active'
ORDER BY e.name;
```

### Find Employees Who Can Re-allocate

```sql
SELECT
    e.name,
    e.employee_name,
    MAX(la.to_date) as last_allocation_end
FROM `tabEmployee` e
LEFT JOIN `tabLeave Allocation` la
    ON la.employee = e.name
    AND la.leave_type = 'Hajj Leave'
    AND la.docstatus = 1
WHERE e.custom_religion = 'Muslim'
  AND e.status = 'Active'
  AND NOT EXISTS (
      SELECT 1
      FROM `tabLeave Application` lapp
      WHERE lapp.employee = e.name
        AND lapp.leave_type = 'Hajj Leave'
        AND lapp.docstatus = 1
        AND lapp.status IN ('Approved', 'Open')
  )
GROUP BY e.name, e.employee_name
HAVING last_allocation_end < CURDATE()
    OR last_allocation_end IS NULL
ORDER BY e.name;
```

---

## Benefits

✅ **Flexible Policy** - Allows re-allocation if not consumed
✅ **Fair to Employees** - Employees who couldn't go for Hajj can try again
✅ **Prevents Abuse** - Once consumed, cannot get again (once-in-service)
✅ **Handles Cancellations** - If cancelled before leave date, can re-apply
✅ **Accurate Tracking** - Tracks **consumption**, not just allocation
✅ **Audit Trail** - Leave Applications show actual Hajj Leave usage

---

## Differences from Old System

| Aspect | Old System | New System |
|--------|-----------|------------|
| Flag Set | On **allocation** | On **Leave Application approval** |
| Re-allocation | Never | If not consumed |
| Cancellation | No effect | Resets flag if before start date |
| Active Allocation | Blocked if exists | Blocked if active **OR** consumed |
| Expiry | Once set, permanent | Can re-allocate if expired unused |

---

## Support

### Reset Hajj Leave Flag (If Needed)

```bash
# Reset for single employee
bench --site hrms.hamptons.om mariadb -e "
UPDATE \`tabEmployee\`
SET custom_hajj_leave_taken = 0,
    custom_hajj_leave_date = NULL
WHERE name = '1002';
"
```

### Check Validation Logs

```bash
# View Leave Control Panel logs
bench --site hrms.hamptons.om show-error-log --doctype "Leave Policy Assignment"
```

---

**Implementation Date:** November 22, 2025
**Policy:** Flexible Once-in-Service
**System:** ERPNext v15 | Frappe v15
**App:** Hamptons v0.0.1
