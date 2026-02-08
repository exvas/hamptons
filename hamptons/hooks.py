app_name = "hamptons"
app_title = "Hamptons"
app_publisher = "sammish"
app_description = "hamptons"
app_email = "sammish.thundiyil@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "hamptons",
# 		"logo": "/assets/hamptons/logo.png",
# 		"title": "Hamptons",
# 		"route": "/hamptons",
# 		"has_permission": "hamptons.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/hamptons/css/hamptons.css"
# app_include_js = "/assets/hamptons/js/hamptons.js"

# include js, css files in header of web template
# web_include_css = "/assets/hamptons/css/hamptons.css"
# web_include_js = "/assets/hamptons/js/hamptons.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "hamptons/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Employee Checkin" : "public/js/employee_checkin.js",
	"Leave Application" : "public/js/leave_application.js",
	"Expense Claim" : "public/js/expense_claim.js"
}
doctype_list_js = {
	"Attendance Regularization" : "public/js/attendance_regularization_list.js"
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "hamptons/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "hamptons.utils.jinja_methods",
# 	"filters": "hamptons.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "hamptons.install.before_install"
# after_install = "hamptons.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "hamptons.uninstall.before_uninstall"
# after_uninstall = "hamptons.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "hamptons.utils.before_app_install"
# after_app_install = "hamptons.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "hamptons.utils.before_app_uninstall"
# after_app_uninstall = "hamptons.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "hamptons.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Department": "hamptons.overrides.department.CustomDepartment"
}

# App startup hooks
# ------------------
after_app_install = "hamptons.overrides.leave_control_panel.override_leave_control_panel"
app_startup = "hamptons.overrides.leave_control_panel.override_leave_control_panel"

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Employee Checkin": {
		"after_insert": "hamptons.overrides.employee_checkin.on_employee_checkin_submit"
	},
	"Leave Allocation": {
		"validate": "hamptons.overrides.leave_allocation.validate_leave_allocation",
		"before_insert": "hamptons.overrides.leave_allocation.validate_leave_allocation",
		"before_submit": "hamptons.overrides.leave_allocation.validate_leave_allocation",
		"on_submit": "hamptons.overrides.leave_allocation.on_submit_leave_allocation"
	},
	"Leave Application": {
		"validate": "hamptons.overrides.leave_application.validate_leave_application",
		"on_update": "hamptons.overrides.leave_application.on_update_leave_application",
		"on_submit": "hamptons.overrides.leave_application.on_submit_leave_application",
		"on_cancel": "hamptons.overrides.leave_application.on_cancel_leave_application"
	},
	"Shift Assignment": {
		"before_insert": "hamptons.overrides.shift_assignment.before_insert_shift_assignment"
	},
	"Attendance Regularization": {
		"after_insert": "hamptons.overrides.attendance_regularization.after_insert_attendance_regularization"
	},
	"Attendance Request": {
		"on_update": "hamptons.overrides.attendance_request.on_update_attendance_request"
	},
	"Expense Claim": {
		"on_update": "hamptons.overrides.expense_claim.on_update_expense_claim"
	}
}

# Scheduled Tasks
# ---------------
scheduler_events = {
	"cron": {
		"*/15 * * * *": [
			"hamptons.hamptons.doctype.crosschex_settings.crosschex_settings.scheduled_attendance_sync"
		],
		"0 2 */5 * *": [
			# Run cleanup every 5 days at 2:00 AM
			"hamptons.utils.cleanup_old_logs"
		],
		"0 20 * * *": [
			# Consolidate daily checkins into Attendance Regularization at 8:00 PM
			"hamptons.overrides.employee_checkin.daily_attendance_regularization_job"
		],
		"0 */4 * * *": [
			# Reconcile missing checkins every 4 hours - catches any missed webhook/sync records
			"hamptons.crosschex_cloud.reconciliation.scheduled_reconciliation_job"
		]
	},
	"hourly": [
		"hamptons.hamptons.doctype.crosschex_settings.crosschex_settings.check_and_refresh_token"
	]
}
# scheduler_events = {
# 	"all": [
# 		"hamptons.tasks.all"
# 	],
# 	"daily": [
# 		"hamptons.tasks.daily"
# 	],
# 	"hourly": [
# 		"hamptons.tasks.hourly"
# 	],
# 	"weekly": [
# 		"hamptons.tasks.weekly"
# 	],
# 	"monthly": [
# 		"hamptons.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "hamptons.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "hamptons.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "hamptons.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["hamptons.utils.before_request"]
# after_request = ["hamptons.utils.after_request"]

# Job Events
# ----------
# before_job = ["hamptons.utils.before_job"]
# after_job = ["hamptons.utils.after_job"]

# User Data Protection
# --------------------
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [
            [
                "name",
                "in",
                [
                    # Employee Custom Fields
                    "Employee-custom_omani_id",
                    "Employee-custom_report_to_name",
                    # Employee Checkin Custom Fields
                    "Employee Checkin-custom_crosschex_uuid",
                    "Employee Checkin-custom_attendance_regularization",
                    # Attendance Custom Fields
                    "Attendance-custom_attendance_regularization",
                    # Leave Policy Custom Fields - Employee
                    "Employee-custom_leave_details_section",
                    "Employee-custom_nationality",
                    "Employee-custom_religion",
                    "Employee-custom_hajj_leave_taken",
                    "Employee-custom_hajj_leave_date",
                    "Employee-custom_leave_column_break",
                    "Employee-custom_leave_carryforward_enabled",
                    "Employee-custom_max_carryforward_days",
                    # Leave Policy Custom Fields - Leave Type
                    "Leave Type-custom_oman_leave_section",
                    "Leave Type-custom_gender_specific",
                    "Leave Type-custom_nationality_specific",
                    "Leave Type-custom_religion_specific",
                    "Leave Type-custom_once_in_service"
                ]
            ]
        ]
    },
    {
        "doctype": "Workspace",
        "filters": [
            [
                "name",
                "in",
                [
                    "Employee Check-in Dashboard"
                ]
            ]
        ]
    },
    {
        "doctype": "Dashboard Chart",
        "filters": [
            [
                "name",
                "in",
                [
                    "Daily Check-ins Overview",
                    "Department-wise Attendance",
                    "Check-in Time Distribution"
                ]
            ]
        ]
    },
    {
        "doctype": "Notification",
        "filters": [
            [
                "name",
                "in",
                [
                    "Leave Application - Notify HOD",
                    "Leave Application - Notify HR After HOD Approval",
                    "Leave Application - Notify GM for HOD/HR Manager",
                    "Leave Application - Notify HR Manager for Direct Staff",
                    "Leave Application - Notify Employee on Approval",
                    "Leave Application - Notify Employee on Rejection"
                ]
            ]
        ]
    }
]
# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"hamptons.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

