frappe.ui.form.on('Employee Checkin', {
  refresh: function(frm) {
    // Hide skip_auto_attendance from users
    frm.toggle_display('skip_auto_attendance', false);
    
    // Add custom button to view dashboard
    if (!frm.is_new()) {
      frm.add_custom_button(__('View Dashboard'), function() {
        frappe.set_route('Workspaces', 'Employee Check-in Dashboard');
      });
      
      // Show employee check-in summary
      show_checkin_summary(frm);
    }
  },
  onload: function(frm) {
    // Always enforce skip auto attendance in background
    if (frm.doc && frm.doc.skip_auto_attendance !== 1) {
      frm.set_value('skip_auto_attendance', 1);
    }
  },
  employee: function(frm) {
    if (frm.doc.employee && !frm.is_new()) {
      show_employee_recent_checkins(frm);
    }
  }
});

function show_checkin_summary(frm) {
  if (!frm.doc.employee || !frm.doc.time) return;
  
  // Get check-in date
  let checkin_date = frappe.datetime.str_to_obj(frm.doc.time);
  let date_str = frappe.datetime.obj_to_str(checkin_date).split(' ')[0];
  
  // Fetch today's check-ins for this employee
  frappe.call({
    method: 'frappe.client.get_list',
    args: {
      doctype: 'Employee Checkin',
      filters: {
        employee: frm.doc.employee,
        time: ['like', date_str + '%']
      },
      fields: ['name', 'time', 'log_type', 'device_id'],
      order_by: 'time asc'
    },
    callback: function(r) {
      if (r.message && r.message.length > 0) {
        let html = '<div class="checkin-summary" style="padding: 10px; background: #f5f7fa; border-radius: 5px; margin: 10px 0;">';
        html += '<h5 style="margin-bottom: 10px; color: #36414c;">Today\'s Check-ins Summary</h5>';
        html += '<table class="table table-bordered" style="margin: 0; background: white;">';
        html += '<thead><tr><th>Time</th><th>Type</th><th>Device</th></tr></thead><tbody>';
        
        r.message.forEach(function(checkin) {
          let time = frappe.datetime.str_to_user(checkin.time);
          let type_color = checkin.log_type === 'IN' ? 'green' : 'red';
          html += `<tr>
            <td>${time}</td>
            <td><span style="color: ${type_color}; font-weight: bold;">${checkin.log_type}</span></td>
            <td>${checkin.device_id || '-'}</td>
          </tr>`;
        });
        
        html += '</tbody></table></div>';
        
        // Display summary in the form
        if (!frm.fields_dict.checkin_summary_html) {
          frm.set_df_property('checkin_summary_html', 'options', html);
        } else {
          frm.get_field('checkin_summary_html').$wrapper.html(html);
        }
      }
    }
  });
}

function show_employee_recent_checkins(frm) {
  // Show recent check-ins for the employee (last 7 days)
  frappe.call({
    method: 'hamptons.hamptons.dashboard_api.get_employee_checkin_details',
    args: {
      employee: frm.doc.employee,
      from_date: frappe.datetime.add_days(frappe.datetime.get_today(), -7),
      to_date: frappe.datetime.get_today()
    },
    callback: function(r) {
      if (r.message && r.message.checkins_by_date) {
        let html = '<div class="recent-checkins" style="padding: 10px; background: #f5f7fa; border-radius: 5px; margin: 10px 0;">';
        html += '<h5 style="margin-bottom: 10px; color: #36414c;">Recent Check-ins (Last 7 Days)</h5>';
        
        r.message.checkins_by_date.forEach(function(day) {
          html += `<div style="margin-bottom: 10px; padding: 8px; background: white; border-radius: 3px;">`;
          html += `<strong>${day.date_formatted}</strong><br>`;
          html += '<small>';
          day.checkins.forEach(function(checkin) {
            let type_color = checkin.log_type === 'IN' ? 'green' : 'red';
            html += `<span style="color: ${type_color};">${checkin.log_type}: ${checkin.time_formatted}</span> `;
          });
          html += '</small></div>';
        });
        
        html += '</div>';
        
        frappe.msgprint({
          title: __('Recent Check-ins'),
          message: html,
          indicator: 'blue'
        });
      }
    }
  });
}
