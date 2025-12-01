// Copyright (c) 2025, sammish and contributors
// For license information, please see license.txt

frappe.query_reports["Consolidate Attendance"] = {
	"filters": [
		{
		  'fieldname': 'from_date',
		  'label': __('From Date'),
		  'fieldtype': 'Date',
		  'reqd': 1,
		},
		{
		  'fieldname': 'to_date',
		  'label': __('To Date'),
		  'fieldtype': 'Date',
		  'reqd': 1,
		},
		{
		  'fieldname': 'employee_id',
		  'label': 'Employee',
		  'fieldtype': 'Link',
		  'options': 'Employee',
		},
		{
		  'fieldname': 'department',
		  'label': 'Department',
		  'fieldtype': 'Link',
		  'options': 'Department',
		},
		{
		  'fieldname': 'att_code',
		  'label': __('Att Code'),
		  'fieldtype': 'Data',
		  'description': __('Enter attendance code to filter specific attendance types')
		}
  	]
};
