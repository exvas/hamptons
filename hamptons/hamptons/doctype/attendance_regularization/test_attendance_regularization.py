# Copyright (c) 2025, Hamptons and contributors
# For license information, please see license.txt

import frappe
import unittest
from frappe.utils import now_datetime, add_days


class TestAttendanceRegularization(unittest.TestCase):
	def setUp(self):
		"""Set up test fixtures"""
		# Create test employee if not exists
		if not frappe.db.exists("Employee", {"employee_name": "Test Employee"}):
			employee = frappe.get_doc({
				"doctype": "Employee",
				"employee_name": "Test Employee",
				"first_name": "Test",
				"last_name": "Employee",
				"gender": "Male",
				"date_of_birth": "1990-01-01",
				"date_of_joining": "2020-01-01",
				"status": "Active"
			})
			employee.insert(ignore_permissions=True)
			self.test_employee = employee.name
		else:
			self.test_employee = frappe.db.get_value("Employee", {"employee_name": "Test Employee"}, "name")
	
	def tearDown(self):
		"""Clean up test data"""
		frappe.db.rollback()
	
	def test_attendance_regularization_creation(self):
		"""Test that Attendance Regularization can be created"""
		ar = frappe.get_doc({
			"doctype": "Attendance Regularization",
			"employee": self.test_employee,
			"time": now_datetime(),
			"log_type": "IN"
		})
		ar.insert()
		self.assertIsNotNone(ar.name)
		self.assertEqual(ar.status, "Open")
	
	def test_validation_missing_employee(self):
		"""Test validation when employee is missing"""
		ar = frappe.get_doc({
			"doctype": "Attendance Regularization",
			"time": now_datetime(),
			"log_type": "IN"
		})
		with self.assertRaises(frappe.ValidationError):
			ar.insert()
	
	def test_validation_missing_time(self):
		"""Test validation when time is missing"""
		ar = frappe.get_doc({
			"doctype": "Attendance Regularization",
			"employee": self.test_employee,
			"log_type": "IN"
		})
		with self.assertRaises(frappe.ValidationError):
			ar.insert()
	
	def test_status_change_on_submit(self):
		"""Test that status changes to Completed on submit"""
		ar = frappe.get_doc({
			"doctype": "Attendance Regularization",
			"employee": self.test_employee,
			"time": now_datetime(),
			"log_type": "IN"
		})
		ar.insert()
		ar.submit()
		self.assertEqual(ar.status, "Completed")
	
	def test_status_change_on_cancel(self):
		"""Test that status changes back to Open on cancel"""
		ar = frappe.get_doc({
			"doctype": "Attendance Regularization",
			"employee": self.test_employee,
			"time": now_datetime(),
			"log_type": "IN"
		})
		ar.insert()
		ar.submit()
		ar.cancel()
		self.assertEqual(ar.status, "Open")