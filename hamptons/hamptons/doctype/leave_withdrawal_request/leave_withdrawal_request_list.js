frappe.listview_settings['Leave Withdrawal Request'] = {
    has_indicator_for_draft: 1,
    get_indicator: function(doc) {
        const status_colors = {
            "Pending": "orange",
            "Approved": "green",
            "Rejected": "red"
        };
        const status = doc.status || "Pending";
        return [__(status), status_colors[status] || "gray", "status,=," + status];
    }
};
