__version__ = "0.0.1"


# Apply monkey patches when app is imported
def _apply_patches():
	"""Apply all monkey patches for the hamptons app"""
	try:
		from hamptons.overrides.leave_control_panel import override_leave_control_panel
		override_leave_control_panel()
	except Exception as e:
		import frappe
		frappe.logger().error(f"Failed to apply hamptons patches: {str(e)}")


# Apply patches on import
_apply_patches()
