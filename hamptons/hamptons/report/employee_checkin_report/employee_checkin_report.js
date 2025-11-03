// Copyright (c) 2024, Momscode and contributors
// For license information, please see license.txt

frappe.query_reports["Employee Checkin Report"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_days(frappe.datetime.get_today(), -30),
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname": "employee",
			"label": __("Employee"),
			"fieldtype": "Link",
			"options": "Employee"
		},
		{
			"fieldname": "department",
			"label": __("Department"),
			"fieldtype": "Link",
			"options": "Department"
		},
		{
			"fieldname": "designation",
			"label": __("Designation"),
			"fieldtype": "Link",
			"options": "Designation"
		},
		{
			"fieldname": "shift",
			"label": __("Shift Type"),
			"fieldtype": "Link",
			"options": "Shift Type"
		},
		{
			"fieldname": "log_type",
			"label": __("Log Type"),
			"fieldtype": "Select",
			"options": "\nIN\nOUT"
		},
		{
			"fieldname": "device_id",
			"label": __("Device ID"),
			"fieldtype": "Data"
		},
		{
			"fieldname": "show_only_late",
			"label": __("Show Only Late Arrivals"),
			"fieldtype": "Check",
			"default": 0
		},
		{
			"fieldname": "show_only_with_regularization",
			"label": __("Show Only With Regularization"),
			"fieldtype": "Check",
			"default": 0
		}
	],
	
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		
		// Highlight late arrivals in red
		if (column.fieldname == "late_by" && data.late_by && data.late_by != "On Time") {
			value = `<span style="color: red; font-weight: bold;">${data.late_by}</span>`;
		}
		
		// Highlight early exits in orange
		if (column.fieldname == "early_exit_by" && data.early_exit_by && data.early_exit_by != "On Time") {
			value = `<span style="color: orange; font-weight: bold;">${data.early_exit_by}</span>`;
		}
		
		// Color code regularization status
		if (column.fieldname == "regularization_status") {
			if (data.regularization_status == "Open") {
				value = `<span style="color: orange;">${data.regularization_status}</span>`;
			} else if (data.regularization_status == "Completed") {
				value = `<span style="color: green;">${data.regularization_status}</span>`;
			} else if (data.regularization_status == "Rejected") {
				value = `<span style="color: red;">${data.regularization_status}</span>`;
			}
		}
		
		return value;
	}
};
