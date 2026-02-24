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
			value = `<span style="color: #dc3545; font-weight: bold;">${data.late_by}</span>`;
		}

		// Highlight early exits in pink
		if (column.fieldname == "early_exit_by" && data.early_exit_by && data.early_exit_by != "On Time") {
			value = `<span style="color: #d63384; font-weight: bold;">${data.early_exit_by}</span>`;
		}

		return value;
	},

	after_datatable_render: function() {
		$('.status-legend').remove();

		var legend = `
		<div class="status-legend" style="margin: 15px 0; padding: 12px 15px; border: 1px solid #eee; border-radius: 4px; background: #fafafa;">
			<h6 style="margin-bottom: 10px; color: #333; font-weight: 600;">Status Legend</h6>
			<div style="display: flex; flex-wrap: wrap;">
				<div style="flex: 1; min-width: 320px;">
					<table style="width: 100%;">
						<tr><td style="padding: 4px 8px;"><span style="color: #28a745; font-weight: bold;">&#9679; Present / OK</span></td><td style="color: #555; font-size: 12px;">Checked in & out, no issues</td></tr>
						<tr><td style="padding: 4px 8px;"><span style="color: #e85d04; font-weight: bold;">&#9679; Pending AR</span></td><td style="color: #555; font-size: 12px;">Regularization pending approval</td></tr>
						<tr><td style="padding: 4px 8px;"><span style="color: #d63384; font-weight: bold;">&#9679; Needs Review</span></td><td style="color: #555; font-size: 12px;">Late / early exit / missing punch, no AR created</td></tr>
					</table>
				</div>
				<div style="flex: 1; min-width: 320px;">
					<table style="width: 100%;">
						<tr><td style="padding: 4px 8px;"><span style="color: #dc3545; font-weight: bold;">&#9679; Absent / Rejected</span></td><td style="color: #555; font-size: 12px;">No record or regularization rejected</td></tr>
						<tr><td style="padding: 4px 8px;"><span style="color: #0d6efd; font-weight: bold;">&#9679; On Leave</span></td><td style="color: #555; font-size: 12px;">On approved leave</td></tr>
						<tr><td style="padding: 4px 8px;"><span style="color: #fd7e14; font-weight: bold;">&#9679; Half Day</span></td><td style="color: #555; font-size: 12px;">Worked a half day</td></tr>
					</table>
				</div>
			</div>
		</div>`;

		$('.report-wrapper').after(legend);
	}
};
