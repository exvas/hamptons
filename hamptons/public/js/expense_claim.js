// Expense Claim customizations for Hamptons
frappe.ui.form.on('Expense Claim', {
    refresh: function(frm) {
        check_expense_attachment(frm);
    },

    before_workflow_action: function(frm) {
        // Require at least one attachment (receipt/invoice) before approval
        let attachments = frm.attachments.get_attachments();
        if (!attachments || attachments.length === 0) {
            frappe.throw(__('Please attach receipts/invoices before submitting this Expense Claim.'));
        }
    },

    before_submit: function(frm) {
        let attachments = frm.attachments.get_attachments();
        if (!attachments || attachments.length === 0) {
            frappe.throw(__('Please attach receipts/invoices before submitting this Expense Claim.'));
        }
    },

    after_save: function(frm) {
        check_expense_attachment(frm);
    }
});

function check_expense_attachment(frm) {
    if (frm.doc.docstatus === 0 && !frm.is_new()) {
        let attachments = frm.attachments ? frm.attachments.get_attachments() : [];
        if (!attachments || attachments.length === 0) {
            frm.dashboard.set_headline_alert(
                __('Please attach receipts/invoices for this Expense Claim.'),
                'orange'
            );
        } else {
            frm.dashboard.clear_headline();
        }
    }
}
