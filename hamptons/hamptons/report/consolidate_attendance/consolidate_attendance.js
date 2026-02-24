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
								report.refresh();
							}
						}
					});
				}
			);
		}).addClass("btn-primary");
	},

	after_datatable_render: function() {
		$('.status-legend').remove();

		var legend = `
		<div class="status-legend" style="margin: 15px 0; padding: 12px 15px; border: 1px solid #eee; border-radius: 4px; background: #fafafa;">
			<h6 style="margin-bottom: 10px; color: #333; font-weight: 600;">Status Legend</h6>
			<div style="display: flex; flex-wrap: wrap;">
				<div style="flex: 1; min-width: 320px;">
					<table style="width: 100%;">
						<tr><td style="padding: 4px 8px;"><span style="color: #28a745; font-weight: bold;">&#9679; Present</span></td><td style="color: #555; font-size: 12px;">Checked in & out within shift rules</td></tr>
						<tr><td style="padding: 4px 8px;"><span style="color: #e85d04; font-weight: bold;">&#9679; Pending AR</span></td><td style="color: #555; font-size: 12px;">Regularization pending approval</td></tr>
						<tr><td style="padding: 4px 8px;"><span style="color: #e6a817; font-weight: bold;">&#9679; Pending</span></td><td style="color: #555; font-size: 12px;">Not yet consolidated</td></tr>
						<tr><td style="padding: 4px 8px;"><span style="color: #d63384; font-weight: bold;">&#9679; Mis-Punch</span></td><td style="color: #555; font-size: 12px;">Missing check-in or check-out</td></tr>
						<tr><td style="padding: 4px 8px;"><span style="color: #dc3545; font-weight: bold;">&#9679; Absent</span></td><td style="color: #555; font-size: 12px;">No attendance record</td></tr>
					</table>
				</div>
				<div style="flex: 1; min-width: 320px;">
					<table style="width: 100%;">
						<tr><td style="padding: 4px 8px;"><span style="color: #5B5EA6; font-weight: bold;">&#9679; Week Off</span></td><td style="color: #555; font-size: 12px;">Scheduled day off</td></tr>
						<tr><td style="padding: 4px 8px;"><span style="color: #7B68AE; font-weight: bold;">&#9679; Week Off (Holiday)</span></td><td style="color: #555; font-size: 12px;">Day off on a holiday</td></tr>
						<tr><td style="padding: 4px 8px;"><span style="color: #9b59b6; font-weight: bold;">&#9679; Holiday</span></td><td style="color: #555; font-size: 12px;">Company / public holiday</td></tr>
						<tr><td style="padding: 4px 8px;"><span style="color: #0d6efd; font-weight: bold;">&#9679; On Leave</span></td><td style="color: #555; font-size: 12px;">On approved leave</td></tr>
						<tr><td style="padding: 4px 8px;"><span style="color: #fd7e14; font-weight: bold;">&#9679; Half Day</span></td><td style="color: #555; font-size: 12px;">Worked a half day</td></tr>
					</table>
				</div>
			</div>
		</div>`;

		$('.report-wrapper').after(legend);
	}
};
