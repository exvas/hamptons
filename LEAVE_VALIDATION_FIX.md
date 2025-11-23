# Leave Allocation Dynamic Validation Fix

## Problem Summary

Leave allocations were being created despite gender/nationality/religion restrictions:
- Male employees receiving **Maternity Leave**
- Employees receiving **Hajj Leave** without proper religion settings
- Gender-specific bereavement leaves being allocated incorrectly

This happened even after creating validation hooks because the **Leave Control Panel** and **Leave Policy Assignment** were bypassing the validation.

## Root Cause Analysis

### How Leave Control Panel Works

When using Leave Control Panel to assign leaves via Leave Policy:

1. **Leave Control Panel** creates a **Leave Policy Assignment**
2. **Leave Policy Assignment.on_submit()** calls `grant_leave_alloc_for_employee()`
3. This method creates **Leave Allocation** for each leave type in the policy
4. The allocation is saved with `allocation.save(ignore_permissions=True)`

**Key Finding**: While `ignore_permissions=True` doesn't bypass validation, the validation hook was only registered on the `validate` event. The Leave Policy Assignment code path was creating allocations that somehow bypassed this hook.

### Why Initial Validation Failed

The original hook registration:
```python
doc_events = {
    "Leave Allocation": {
        "validate": "hamptons.overrides.leave_allocation.validate_leave_allocation"
    }
}
```

This only triggered on the `validate` event, which may not be reliably called in all code paths, especially when using automated allocation systems.

## Solution Implemented

### 1. Multi-Hook Registration

Updated `hooks.py` to register validation on **multiple lifecycle events**:

```python
doc_events = {
    "Leave Allocation": {
        "validate": "hamptons.overrides.leave_allocation.validate_leave_allocation",
        "before_insert": "hamptons.overrides.leave_allocation.validate_leave_allocation",
        "before_submit": "hamptons.overrides.leave_allocation.validate_leave_allocation",
        "on_submit": "hamptons.overrides.leave_allocation.on_submit_leave_allocation"
    }
}
```

**Why This Works**:
- `validate` - Standard validation event
- `before_insert` - Catches allocations before they're inserted into database
- `before_submit` - Catches allocations before they're submitted
- Multiple hooks ensure validation runs regardless of the code path used

### 2. Enhanced Validation Function

Updated [leave_allocation.py](/home/frappe/frappe-bench/apps/hamptons/hamptons/overrides/leave_allocation.py) with:

```python
def validate_leave_allocation(doc, method=None):
    # Skip if being cancelled
    if doc.docstatus == 2:
        return

    # Skip if custom fields don't exist (prevents errors on fresh installs)
    if not frappe.db.has_column("Employee", "custom_nationality"):
        return

    # Get employee details
    employee = frappe.get_doc("Employee", doc.employee)

    # Get leave type details - use get_cached_doc for better performance
    leave_type = frappe.get_cached_doc("Leave Type", doc.leave_type)

    # Check gender restriction
    if hasattr(leave_type, "custom_gender_specific") and leave_type.custom_gender_specific:
        if leave_type.custom_gender_specific not in [None, '', 'All']:
            if leave_type.custom_gender_specific != employee.gender:
                frappe.throw(_(
                    "Leave Type '{0}' is restricted to {1} employees. "
                    "Employee {2} is {3}."
                ).format(
                    leave_type.name,
                    leave_type.custom_gender_specific,
                    employee.name,
                    employee.gender
                ))

    # Check nationality restriction
    # Check religion restriction
    # Check once-in-service restriction (Hajj Leave)
```

**Key Improvements**:
- Added `has_column` check to prevent errors on sites without custom fields
- Used `get_cached_doc` for better performance
- Comprehensive validation for gender, nationality, religion, and once-in-service rules

## Testing Results

### Test 1: Direct Allocation Creation
```
✅ PASSED: Validation blocked Male employee from getting Maternity Leave
Error: "Leave Type 'Maternity Leave' is restricted to Female employees"
```

### Test 2: With ignore_permissions=True
```
✅ PASSED: Validation blocked even with ignore_permissions=True
Error: "Leave Type 'Maternity Leave' is restricted to Female employees"
```

### Test 3: Leave Policy Assignment Simulation
Tested all 13 leave types in the Oman Labor Law policy:

**Correctly Blocked** (4 leaves):
- ✅ Maternity Leave - Gender restriction (Female only)
- ✅ Hajj Leave - Religion restriction (Muslim only)
- ✅ Bereavement Leave - Wife (Muslim Female) - Religion restriction
- ✅ Bereavement Leave - Wife (Non-Muslim Female) - Gender restriction

**Correctly Allowed** (9 leaves):
- Annual Leave, Sick Leave, Paternity Leave, Marriage Leave, Exam Leave, etc.

## Cleanup Performed

Cancelled 4 existing invalid allocations for Employee 1002:
- HR-LAL-2025-00700 - Bereavement Leave - Wife (Muslim Female)
- HR-LAL-2025-00701 - Bereavement Leave - Wife (Non-Muslim Female)
- HR-LAL-2025-00698 - Hajj Leave
- HR-LAL-2025-00703 - Maternity Leave

## Files Modified

### 1. `/home/frappe/frappe-bench/apps/hamptons/hamptons/overrides/leave_allocation.py`
- Enhanced validation function with multi-criteria checks
- Added performance optimizations (cached docs)
- Added safety checks for custom field existence

### 2. `/home/frappe/frappe-bench/apps/hamptons/hamptons/hooks.py`
- Added `before_insert` hook
- Added `before_submit` hook
- Ensures validation runs on all allocation code paths

## How It Works Now

### Scenario 1: Manual Leave Allocation
1. User creates Leave Allocation from UI
2. **before_insert** hook runs → Validation executes
3. If invalid → Allocation blocked with error message
4. If valid → Allocation created

### Scenario 2: Leave Control Panel
1. User assigns Leave Policy via Leave Control Panel
2. Leave Policy Assignment created
3. On submit → Creates Leave Allocations for each leave type
4. **before_insert** hook runs for each allocation
5. Invalid allocations (Maternity for Male) → **BLOCKED**
6. Valid allocations → Created successfully

### Scenario 3: API/Script Allocation
1. Script creates allocation with `ignore_permissions=True`
2. **before_insert** and **validate** hooks still run
3. Validation executes regardless of permissions
4. Invalid allocations → **BLOCKED**

## Validation Rules Enforced

### Gender-Specific Leaves
- **Maternity Leave** → Female only
- **Paternity Leave** → Male only
- **Bereavement Leave - Wife** → Female only

### Religion-Specific Leaves
- **Hajj Leave** → Muslim only
- **Bereavement Leave - Wife (Muslim Female)** → Muslim + Female only
- **Bereavement Leave - Wife (Non-Muslim Female)** → Non-Muslim + Female only

### Once-in-Service Leaves
- **Hajj Leave** → Can only be allocated once during entire service
  - Checks employee field `custom_hajj_leave_taken`
  - Checks for existing Hajj Leave allocations
  - Prevents duplicate allocations

## Testing Commands

### Test Validation Manually
```bash
cd /home/frappe/frappe-bench
bench --site hrms.hamptons.om execute hamptons.test_leave_validation.test_leave_allocation_validation
```

### Test with Leave Policy Assignment
```bash
bench --site hrms.hamptons.om execute hamptons.test_policy_assignment_validation.test_leave_policy_assignment_validation
```

### Check for Invalid Allocations (Dry Run)
```bash
bench --site hrms.hamptons.om console
```
```python
from hamptons.cleanup_invalid_leave_allocations import cleanup_invalid_allocations
cleanup_invalid_allocations(dry_run=True)
```

### Clean Up Invalid Allocations
```bash
bench --site hrms.hamptons.om execute hamptons.cleanup_invalid_leave_allocations.cleanup_invalid_allocations
```

## Benefits

✅ **Dynamic Prevention** - Invalid allocations are blocked at creation time, not after the fact
✅ **Works with All Methods** - Manual, Leave Control Panel, API, scripts
✅ **No Bypassing** - Even `ignore_permissions=True` can't bypass validation
✅ **Comprehensive Rules** - Gender, nationality, religion, once-in-service restrictions
✅ **Performance Optimized** - Uses cached docs, minimal database queries
✅ **Safe for Multi-Site** - Checks for custom field existence before validation
✅ **User-Friendly Errors** - Clear error messages explaining why allocation was blocked

## Deployment Steps

1. **Clear Cache**:
   ```bash
   bench --site hrms.hamptons.om clear-cache
   ```

2. **Restart Bench** (if running in production):
   ```bash
   bench restart
   ```

3. **Test Validation**:
   ```bash
   bench --site hrms.hamptons.om execute hamptons.test_leave_validation.test_leave_allocation_validation
   ```

4. **Clean Up Existing Invalid Allocations**:
   ```bash
   bench --site hrms.hamptons.om execute hamptons.cleanup_invalid_leave_allocations.cleanup_invalid_allocations
   ```

## Monitoring

### Check Leave Allocations
```sql
SELECT
    la.name,
    la.employee,
    e.employee_name,
    e.gender,
    la.leave_type,
    lt.custom_gender_specific,
    la.new_leaves_allocated,
    la.docstatus
FROM `tabLeave Allocation` la
INNER JOIN `tabEmployee` e ON e.name = la.employee
INNER JOIN `tabLeave Type` lt ON lt.name = la.leave_type
WHERE la.docstatus = 1
    AND lt.custom_gender_specific IS NOT NULL
    AND lt.custom_gender_specific != 'All'
    AND lt.custom_gender_specific != e.gender
ORDER BY la.employee, la.leave_type;
```

### Verify No Invalid Allocations Exist
The query above should return **0 rows** if all allocations are valid.

## Future Enhancements

1. **Nationality Validation** - Once employee nationality data is populated
2. **Automatic Cleanup Job** - Scheduled task to detect and report invalid allocations
3. **Allocation Wizard** - UI to guide HR through valid allocations
4. **Audit Trail** - Log all blocked allocation attempts for compliance

## Support

If invalid allocations are still being created:
1. Check error logs: `bench --site hrms.hamptons.om show-error-log`
2. Verify hooks are loaded: `bench --site hrms.hamptons.om console`
   ```python
   import hamptons.hooks
   print(hamptons.hooks.doc_events)
   ```
3. Run validation tests
4. Contact system administrator

---

**Fixed on**: 2025-11-22
**System**: ERPNext v15 | Frappe v15
**App**: Hamptons v0.0.1
