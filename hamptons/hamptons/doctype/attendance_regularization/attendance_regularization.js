// Copyright (c) 2025, Hamptons and contributors
// For license information, please see license.txt

frappe.ui.form.on('Attendance Regularization', {
	refresh: function(frm) {
		// Set indicator based on status
		if (frm.doc.status === 'Completed') {
			frm.page.set_indicator(__('Completed'), 'green');
		} else {
			frm.page.set_indicator(__('Open'), 'orange');
		}
		
		// Show submit button only if document is not yet submitted
		if (!frm.doc.__islocal && frm.doc.docstatus === 0) {
			frm.page.set_primary_action(__('Submit'), function() {
				frm.savesubmit();
			});
		}
	},
	
	employee: function(frm) {
		// Fetch employee details when employee is selected
		if (frm.doc.employee) {
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Employee',
					name: frm.doc.employee
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('employee_name', r.message.employee_name);
						frm.set_value('reports_to', r.message.reports_to);
					}
				}
			});
		}
	},
	
	shift: function(frm) {
		// Fetch shift times when shift is selected
		if (frm.doc.shift) {
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Shift Type',
					name: frm.doc.shift
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('start_time', r.message.start_time);
						frm.set_value('end_time', r.message.end_time);
					}
				}
			});
		}
	},
	
	time: function(frm) {
		// Calculate late time when time is changed
		if (frm.doc.time && frm.doc.shift && frm.doc.start_time) {
			calculate_late_time(frm);
		}
	}
});

function calculate_late_time(frm) {
	// Calculate how late the employee was
	if (frm.doc.log_type === 'IN' && frm.doc.time && frm.doc.start_time) {
		let check_time = moment(frm.doc.time);
		let shift_start = moment(frm.doc.time).format('YYYY-MM-DD') + ' ' + frm.doc.start_time;
		let shift_start_time = moment(shift_start);
		
		if (check_time.isAfter(shift_start_time)) {
			let diff = moment.duration(check_time.diff(shift_start_time));
			let hours = Math.floor(diff.asHours());
			let minutes = Math.floor(diff.asMinutes()) % 60;
			let seconds = Math.floor(diff.asSeconds()) % 60;
			
			let late_time = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
			frm.set_value('late', late_time);
		} else {
			frm.set_value('late', null);
		}
	}
}