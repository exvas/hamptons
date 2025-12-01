# Copyright (c) 2025, sammish and contributors
# For license information, please see license.txt

import frappe

no_cache = 1

def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False

    # Pass user info to template
    context.user = frappe.session.user
    context.is_logged_in = frappe.session.user != "Guest"

    # Get employee info if logged in
    if context.is_logged_in:
        employee = frappe.db.get_value(
            "Employee",
            {"user_id": frappe.session.user},
            ["name", "employee_name"],
            as_dict=True
        )
        context.employee = employee
    else:
        context.employee = None

    return context
