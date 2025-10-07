// Copyright (c) 2025, sammish and contributors
// For license information, please see license.txt

frappe.ui.form.on('Crosschex Settings', {
    refresh: function(frm) {
        // Add custom buttons
        frm.add_custom_button(__('Test Connection'), function() {
            test_api_connection(frm);
        });
        
        frm.add_custom_button(__('Sync Now'), function() {
            manual_sync_now(frm);
        });
        
        frm.add_custom_button(__('Clear Logs'), function() {
            clear_crosschex_logs(frm);
        });
        
        frm.add_custom_button(__('Reset Token'), function() {
            reset_api_token(frm);
        });
        
        // Show status indicators
        update_status_indicators(frm);
    },
    
    enable_realtime_sync: function(frm) {
        if (frm.doc.enable_realtime_sync) {
            frappe.msgprint({
                title: __('CrossChex Sync Enabled'),
                message: __('Please ensure API credentials are configured and test the connection.'),
                indicator: 'blue'
            });
        }
    },
    
    test_connection_btn: function(frm) {
        test_api_connection(frm);
    },
    
    sync_now_btn: function(frm) {
        manual_sync_now(frm);
    },
    
    clear_logs_btn: function(frm) {
        clear_crosschex_logs(frm);
    },
    
    reset_token_btn: function(frm) {
        reset_api_token(frm);
    },
    
    api_key: function(frm) {
        if (frm.doc.api_key) {
            frm.set_value('connection_status', 'Not Tested');
        }
    },
    
    api_secret: function(frm) {
        if (frm.doc.api_secret) {
            frm.set_value('connection_status', 'Not Tested');
        }
    }
});

// Child table: CrossChex API Configuration
frappe.ui.form.on('CrossChex API Configuration', {
    api_configurations_add: function(frm, cdt, cdn) {
        // Set default values for new row
        let row = locals[cdt][cdn];
        if (!row.api_url) {
            frappe.model.set_value(cdt, cdn, 'connection_status', 'Not Tested');
        }
    },
    
    // Handle Test Connection button click
    test_connection: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        test_individual_connection(frm, row);
    },
    
    // Handle Sync Now button click
    sync_now: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        sync_individual_device(frm, row);
    }
});

function test_individual_connection(frm, config_row) {
    if (!config_row.api_url || !config_row.api_key || !config_row.api_secret) {
        frappe.msgprint({
            title: __('Missing Information'),
            message: __('Please fill in API URL, API Key, and API Secret before testing.'),
            indicator: 'orange'
        });
        return;
    }
    
    // Check if the document is saved
    if (!config_row.name || config_row.name.startsWith('new-')) {
        frappe.msgprint({
            title: __('Save Required'),
            message: __('Please save the document first before testing the connection. Password fields are only stored after saving.'),
            indicator: 'orange'
        });
        return;
    }
    
    frappe.call({
        method: 'hamptons.hamptons.doctype.crosschex_settings.crosschex_settings.test_individual_api_config',
        args: {
            api_url: config_row.api_url,
            api_key: config_row.api_key,
            config_row_name: config_row.name,
            config_name: config_row.configuration_name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint({
                    title: __('Success'),
                    message: __('Connection to {0} successful!', [config_row.configuration_name || config_row.api_url]),
                    indicator: 'green'
                });
                
                // Update the row's connection status
                frappe.model.set_value(config_row.doctype, config_row.name, 'connection_status', 'Connected');
                frappe.model.set_value(config_row.doctype, config_row.name, 'token', r.message.token);
                if (r.message.expires) {
                    frappe.model.set_value(config_row.doctype, config_row.name, 'token_expires', r.message.expires);
                }
                frappe.model.set_value(config_row.doctype, config_row.name, 'last_token_generated', frappe.datetime.now_datetime());
                
                frm.refresh_field('api_configurations');
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message ? r.message.error : __('Connection failed'),
                    indicator: 'red'
                });
                
                // Update the row's connection status
                frappe.model.set_value(config_row.doctype, config_row.name, 'connection_status', 'Error');
                frm.refresh_field('api_configurations');
            }
        }
    });
}

function sync_individual_device(frm, config_row) {
    if (!config_row.api_url || !config_row.api_key || !config_row.api_secret) {
        frappe.msgprint({
            title: __('Missing Information'),
            message: __('Please fill in API URL, API Key, and API Secret before syncing.'),
            indicator: 'orange'
        });
        return;
    }
    
    // Check if the document is saved
    if (!config_row.name || config_row.name.startsWith('new-')) {
        frappe.msgprint({
            title: __('Save Required'),
            message: __('Please save the document first before syncing.'),
            indicator: 'orange'
        });
        return;
    }
    
    // Show progress indicator
    frappe.show_alert({
        message: __('Starting sync for {0}...', [config_row.configuration_name || config_row.api_url]),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'hamptons.hamptons.doctype.crosschex_settings.crosschex_settings.sync_individual_device',
        args: {
            api_url: config_row.api_url,
            api_key: config_row.api_key,
            config_row_name: config_row.name,
            config_name: config_row.configuration_name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint({
                    title: __('Success'),
                    message: __('Sync completed for {0}! Processed {1} records.',
                        [config_row.configuration_name || config_row.api_url, r.message.processed || 0]),
                    indicator: 'green'
                });
                
                // Update sync status fields
                frappe.model.set_value(config_row.doctype, config_row.name, 'last_sync_time', frappe.datetime.now_datetime());
                frappe.model.set_value(config_row.doctype, config_row.name, 'last_sync_status',
                    `Success - ${r.message.processed || 0} records processed`);
                
                frm.refresh_field('api_configurations');
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message ? r.message.error : __('Sync failed'),
                    indicator: 'red'
                });
                
                // Update sync status with error
                frappe.model.set_value(config_row.doctype, config_row.name, 'last_sync_status',
                    `Error: ${r.message ? r.message.error : 'Unknown error'}`);
                frm.refresh_field('api_configurations');
            }
        }
    });
}

function test_api_connection(frm) {
    frappe.call({
        method: 'test_connection',
        doc: frm.doc,
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint({
                    title: __('Success'),
                    message: r.message.message,
                    indicator: 'green'
                });
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message ? r.message.error : __('Connection failed'),
                    indicator: 'red'
                });
            }
        }
    });
}

function manual_sync_now(frm) {
    frappe.call({
        method: 'sync_now',
        doc: frm.doc,
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint({
                    title: __('Success'),
                    message: r.message.message,
                    indicator: 'green'
                });
                frm.reload_doc();
            } else {
                frappe.msgprint({
                    title: __('Error'), 
                    message: r.message ? r.message.error : __('Sync failed'),
                    indicator: 'red'
                });
            }
        }
    });
}

function clear_crosschex_logs(frm) {
    frappe.confirm(__('Clear all CrossChex logs?'), function() {
        frappe.call({
            method: 'clear_logs',
            doc: frm.doc,
            callback: function(r) {
                frappe.msgprint({
                    title: r.message.success ? __('Success') : __('Error'),
                    message: r.message.success ? r.message.message : r.message.error,
                    indicator: r.message.success ? 'green' : 'red'
                });
            }
        });
    });
}

function reset_api_token(frm) {
    frappe.confirm(__('Reset API token?'), function() {
        frappe.call({
            method: 'reset_token',
            doc: frm.doc,
            callback: function(r) {
                frappe.msgprint({
                    title: r.message.success ? __('Success') : __('Error'),
                    message: r.message.success ? r.message.message : r.message.error,
                    indicator: r.message.success ? 'green' : 'red'
                });
                if (r.message.success) {
                    frm.refresh();
                }
            }
        });
    });
}

function update_status_indicators(frm) {
    let status = frm.doc.connection_status || 'Not Tested';
    let indicator_class = 'gray';
    
    switch(status) {
        case 'Connected':
            indicator_class = 'green';
            break;
        case 'Disconnected':
            indicator_class = 'orange';
            break;
        case 'Error':
            indicator_class = 'red';
            break;
        default:
            indicator_class = 'gray';
    }
    
    // Show sync status
    if (frm.doc.enable_realtime_sync && frm.doc.last_sync_time) {
        let last_sync = moment(frm.doc.last_sync_time);
        let time_ago = last_sync.fromNow();
        
        frm.dashboard.set_headline(__('Last sync: {0}', [time_ago]));
    }
    
    // Add status indicator
    let $status_html = $(`
        <div style="margin: 10px 0;">
            <span class="indicator ${indicator_class}">${__('Connection')}: ${__(status)}</span>
            ${frm.doc.enable_realtime_sync ? '<span class="indicator blue" style="margin-left: 10px;">' + __('Sync Enabled') + '</span>' : ''}
        </div>
    `);
    
    frm.page.set_indicator(__(status), indicator_class);
}