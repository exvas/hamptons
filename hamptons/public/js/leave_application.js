// Leave Application customizations for Hamptons
frappe.ui.form.on('Leave Application', {
    refresh: function(frm) {
        // Add Withdraw button for approved leave applications
        if (frm.doc.docstatus === 1 && frm.doc.status === 'Approved') {
            // Check if leave hasn't ended yet
            if (frappe.datetime.get_diff(frm.doc.to_date, frappe.datetime.nowdate()) >= 0) {
                // Check for existing pending withdrawal request
                frappe.call({
                    method: 'frappe.client.get_count',
                    args: {
                        doctype: 'Leave Withdrawal Request',
                        filters: {
                            leave_application: frm.doc.name,
                            status: 'Pending',
                            docstatus: 0
                        }
                    },
                    callback: function(r) {
                        if (r.message === 0) {
                            frm.add_custom_button(__('Withdraw Leave'), function() {
                                show_withdraw_dialog(frm);
                            }, __('Actions'));
                        } else {
                            frm.add_custom_button(__('View Withdrawal Request'), function() {
                                frappe.set_route('List', 'Leave Withdrawal Request', {
                                    leave_application: frm.doc.name
                                });
                            }, __('Actions'));
                        }
                    }
                });
            }
        }
    }
});

function show_withdraw_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Withdraw Leave Application'),
        fields: [
            {
                label: __('Leave Details'),
                fieldname: 'leave_details',
                fieldtype: 'HTML',
                options: `
                    <div class="leave-details" style="margin-bottom: 15px; padding: 10px; background: #f5f5f5; border-radius: 5px;">
                        <p><strong>${__('Leave Type')}:</strong> ${frm.doc.leave_type}</p>
                        <p><strong>${__('From')}:</strong> ${frappe.datetime.str_to_user(frm.doc.from_date)}</p>
                        <p><strong>${__('To')}:</strong> ${frappe.datetime.str_to_user(frm.doc.to_date)}</p>
                        <p><strong>${__('Days')}:</strong> ${frm.doc.total_leave_days}</p>
                    </div>
                `
            },
            {
                label: __('Reason for Withdrawal'),
                fieldname: 'reason',
                fieldtype: 'Small Text',
                reqd: 1,
                description: __('Please provide a reason for withdrawing this leave')
            }
        ],
        primary_action_label: __('Submit Withdrawal Request'),
        primary_action: function(values) {
            frappe.call({
                method: 'hamptons.hamptons.doctype.leave_withdrawal_request.leave_withdrawal_request.create_withdrawal_request',
                args: {
                    leave_application: frm.doc.name,
                    reason: values.reason
                },
                freeze: true,
                freeze_message: __('Submitting withdrawal request...'),
                callback: function(r) {
                    if (r.message) {
                        d.hide();
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'green'
                        }, 5);
                        frm.reload_doc();
                    }
                }
            });
        }
    });
    d.show();
}
