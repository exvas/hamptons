// Copyright (c) 2026, sammish and contributors
// For license information, please see license.txt

frappe.query_reports["Employee Details Report"] = {
	"filters": [
		{
			'fieldname': 'employee',
			'label': __('Employee'),
			'fieldtype': 'Link',
			'options': 'Employee',
		},
		{
			'fieldname': 'department',
			'label': __('Department'),
			'fieldtype': 'Link',
			'options': 'Department',
		},
		{
			'fieldname': 'designation',
			'label': __('Designation'),
			'fieldtype': 'Link',
			'options': 'Designation',
		},
		{
			'fieldname': 'branch',
			'label': __('Branch'),
			'fieldtype': 'Link',
			'options': 'Branch',
		},
		{
			'fieldname': 'nationality',
			'label': __('Nationality'),
			'fieldtype': 'Link',
			'options': 'Country',
		},
		{
			'fieldname': 'religion',
			'label': __('Religion'),
			'fieldtype': 'Data',
		},
		{
			'fieldname': 'reports_to',
			'label': __('Reports To'),
			'fieldtype': 'Link',
			'options': 'Employee',
		},
	]
};
