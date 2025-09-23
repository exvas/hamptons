
# Create a test department to verify our override
company = frappe.get_doc('Company', {'company_name': 'Hampton Test Company'}) if frappe.db.exists('Company', 'Hampton Test Company') else frappe.get_doc({
    'doctype': 'Company',
    'company_name': 'Hampton Test Company',
    'abbr': 'HTC',
    'default_currency': 'USD'
}).insert()

# Test department creation
dept = frappe.new_doc('Department')
dept.department_name = 'sss'
dept.company = 'Hampton Test Company'

# Save the department
dept.save()

print('Department Name (ID):', dept.name)
print('Department Display Name:', dept.department_name)
print('Expected: sss (not sss - HTC)')

