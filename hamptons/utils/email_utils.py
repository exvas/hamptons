# Copyright (c) 2024, Hamptons and contributors
# For license information, please see license.txt

"""
Email utility functions for Hamptons app.

These functions ensure emails are only sent via properly configured
and enabled Frappe Email Accounts.
"""

import frappe
from frappe import _


def is_outgoing_email_enabled():
    """
    Check if there is an enabled outgoing email account.

    Returns:
        bool: True if at least one Email Account has enable_outgoing=1
    """
    enabled_account = frappe.db.exists(
        "Email Account",
        {
            "enable_outgoing": 1
        }
    )
    return bool(enabled_account)


def get_default_outgoing_email_account():
    """
    Get the default outgoing email account if one exists and is enabled.

    Returns:
        Email Account doc or None
    """
    # First try to get the default outgoing account
    default_account = frappe.db.get_value(
        "Email Account",
        {
            "enable_outgoing": 1,
            "default_outgoing": 1
        },
        "name"
    )

    if default_account:
        return frappe.get_doc("Email Account", default_account)

    # If no default, try to get any enabled outgoing account
    any_account = frappe.db.get_value(
        "Email Account",
        {
            "enable_outgoing": 1
        },
        "name"
    )

    if any_account:
        return frappe.get_doc("Email Account", any_account)

    return None


def send_email_if_enabled(recipients, subject, message, reference_doctype=None, reference_name=None, now=False):
    """
    Send email only if there is an enabled outgoing email account.

    This function wraps frappe.sendmail() and adds a check for enabled
    outgoing email accounts before attempting to send.

    Args:
        recipients: List of recipient email addresses
        subject: Email subject
        message: Email body (HTML)
        reference_doctype: Optional reference doctype
        reference_name: Optional reference document name
        now: If True, send immediately instead of queuing

    Returns:
        bool: True if email was sent/queued, False if no enabled account
    """
    if not is_outgoing_email_enabled():
        frappe.logger().warning(
            f"Email not sent - no enabled outgoing email account. "
            f"Subject: {subject}, Recipients: {recipients}"
        )
        return False

    try:
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=message,
            reference_doctype=reference_doctype,
            reference_name=reference_name,
            now=now
        )
        return True
    except Exception as e:
        frappe.logger().error(f"Failed to send email: {str(e)}")
        return False
