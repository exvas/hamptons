# Copyright (c) 2024, sammish and Contributors
# License: MIT

import frappe
from frappe.utils.nestedset import get_root_of
from erpnext.setup.doctype.department.department import Department


class CustomDepartment(Department):
	"""
	Custom Department class that overrides the default naming behavior.
	Instead of appending company abbreviation (e.g., "sss - H"), 
	it keeps the department name as entered (e.g., "sss").
	"""
	
	def autoname(self):
		"""
		Override the default autoname method to prevent company abbreviation
		from being appended to the department name.
		"""
		root = get_root_of("Department")
		if root and self.department_name != root:
			# Use department name as-is without company abbreviation
			self.name = self.department_name
		else:
			self.name = self.department_name

	def before_rename(self, old, new, merge=False):
		"""
		Override the before_rename method to prevent automatic abbreviation
		addition during rename operations.
		"""
		# Return the new name as-is without adding company abbreviation
		return new