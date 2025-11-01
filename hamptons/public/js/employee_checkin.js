frappe.ui.form.on('Employee Checkin', {
  refresh: function(frm) {
    // Hide skip_auto_attendance from users
    frm.toggle_display('skip_auto_attendance', false);
  },
  onload: function(frm) {
    // Always enforce skip auto attendance in background
    if (frm.doc && frm.doc.skip_auto_attendance !== 1) {
      frm.set_value('skip_auto_attendance', 1);
    }
  }
});
