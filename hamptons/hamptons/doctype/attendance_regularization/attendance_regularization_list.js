frappe.listview_settings['Attendance Regularization'] = {
  onload: function(listview) {
    const runSync = function() {
      frappe.confirm(__('Run manual sync for yesterday and last 365 days?<br><br>This will run in the background and may take several minutes.'), () => {
        // Show progress dialog
        const progress = frappe.show_progress(
          __('Starting Sync'),
          0,
          100,
          __('Queuing background job...'),
          true
        );

        frappe.call({
          method: 'hamptons.overrides.employee_checkin.run_attendance_regularization_sync',
          args: { days: 365, include_yesterday: 1 },
          callback: function(r) {
            // Hide progress dialog
            frappe.hide_progress();

            if (r.message && r.message.success) {
              frappe.msgprint({
                title: __('Sync Job Started'),
                message: __('Background job queued successfully.<br><br>{0}<br><br>Processing {1} days from {2} to {3}.<br><br>{4}', [
                  r.message.message || '',
                  365,
                  r.message.start_date,
                  r.message.end_date,
                  r.message.note || 'Check the list in a few minutes for results.'
                ]),
                indicator: 'blue',
                primary_action: {
                  label: __('Refresh List'),
                  action: function() {
                    listview.refresh();
                  }
                }
              });
            } else {
              frappe.msgprint({
                title: __('Sync Failed'),
                message: r.message && r.message.error ? r.message.error : __('Failed to start sync job'),
                indicator: 'red'
              });
            }
          },
          error: function(r) {
            frappe.hide_progress();
            frappe.msgprint({
              title: __('Sync Error'),
              message: __('An error occurred while starting the sync job'),
              indicator: 'red'
            });
          }
        });
      });
    };

    // Add single RUN button to toolbar
    listview.page.add_inner_button(__('RUN'), runSync);
  }
};
