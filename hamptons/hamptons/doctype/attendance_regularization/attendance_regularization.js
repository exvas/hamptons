frappe.ui.form.on('Attendance Regularization', {
	refresh: function(frm) {
		// Refresh child table to ensure all fields are displayed
		if (!frm.is_new()) {
			frm.refresh_field('attendance_regularization_item');
		}

		// Add Approve button for Pending status
		if (frm.doc.status === 'Pending' && !frm.is_new()) {
			frm.add_custom_button(__('Approve'), function() {
				frappe.confirm(
					__('Are you sure you want to approve this regularization request?<br>This will create a Present attendance record.'),
					function() {
						frm.call({
							method: 'approve',
							doc: frm.doc,
							callback: function(r) {
								if (!r.exc) {
									frm.reload_doc();
								}
							}
						});
					}
				);
			}, __('Actions'));

			// Add Reject button
			frm.add_custom_button(__('Reject'), function() {
				frappe.confirm(
					__('Are you sure you want to reject this regularization request?<br>This will create an Absent attendance record.'),
					function() {
						frm.call({
							method: 'reject',
							doc: frm.doc,
							callback: function(r) {
								if (!r.exc) {
									frm.reload_doc();
								}
							}
						});
					}
				);
			}, __('Actions'));

			// Make Approve button primary (green)
			frm.page.set_primary_action(__('Approve'), function() {
				frappe.confirm(
					__('Are you sure you want to approve this regularization request?<br>This will create a Present attendance record.'),
					function() {
						frm.call({
							method: 'approve',
							doc: frm.doc,
							callback: function(r) {
								if (!r.exc) {
									frm.reload_doc();
								}
							}
						});
					}
				);
			});
		}

		// Show indicator based on status
		if (frm.doc.status === 'Approved') {
			frm.dashboard.set_headline_alert(__('Approved - Attendance marked as Present'), 'green');
		} else if (frm.doc.status === 'Rejected') {
			frm.dashboard.set_headline_alert(__('Rejected - Attendance marked as Absent'), 'red');
		} else if (frm.doc.status === 'Pending') {
			frm.dashboard.set_headline_alert(__('Pending Approval'), 'orange');
		}
	},

	// Add Fetch Shift button to manually fetch shift details
	posting_date: function(frm) {
		if (frm.doc.employee && frm.doc.posting_date) {
			frm.call({
				method: 'fetch_shift_details',
				doc: frm.doc,
				callback: function(r) {
					if (r.message) {
						frm.refresh_fields();
					}
				}
			});
		}
	},

	onload: function(frm) {
		// Ensure child table fields are properly loaded
		if (!frm.is_new() && frm.doc.attendance_regularization_item) {
			frm.refresh_field('attendance_regularization_item');
		}
	}
});

// Add child table event handler to ensure fields are displayed
frappe.ui.form.on('Attendance Regularization Item', {
	attendance_regularization_item_add: function(frm, cdt, cdn) {
		// Refresh the row when added
		frm.refresh_field('attendance_regularization_item');
	}
});
