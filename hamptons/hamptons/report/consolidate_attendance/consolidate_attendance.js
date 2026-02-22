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
	],

	onload: function(report) {
		report.page.add_inner_button(__("Consolidate Pending"), function() {
			let from_date = report.get_filter_value('from_date');
			let to_date = report.get_filter_value('to_date');

			if (!from_date || !to_date) {
				frappe.msgprint(__("Please set From Date and To Date filters first."));
				return;
			}

			frappe.confirm(
				__("This will create Attendance records for all dates with checkins but no attendance between {0} and {1}. Continue?",
					[from_date, to_date]),
				function() {
					frappe.call({
						method: "hamptons.overrides.employee_checkin.consolidate_pending_attendance",
						args: {
							from_date: from_date,
							to_date: to_date
						},
						freeze: true,
						freeze_message: __("Processing pending attendance..."),
						callback: function(r) {
							if (r.message) {
								let stats = r.message;
								frappe.msgprint({
									title: __("Consolidation Complete"),
									indicator: "green",
									message: stats.message
								});
								// Refresh the report
								report.refresh();
							}
						}
					});
				}
			);
		}).addClass("btn-primary");
	}
};
