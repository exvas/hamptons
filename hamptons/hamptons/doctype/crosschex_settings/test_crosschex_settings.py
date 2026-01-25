import frappe
import unittest


class TestCrosschexSettings(unittest.TestCase):

    def test_crosschex_settings_creation(self):
        """Test that CrossChex Settings doctype can be created"""
        settings = frappe.get_single("Crosschex Settings")
        self.assertIsNotNone(settings)

    def test_validation_with_missing_api_configurations(self):
        """Test validation when sync is enabled but no API configurations exist"""
        settings = frappe.get_single("Crosschex Settings")
        settings.enable_realtime_sync = 1
        settings.api_configurations = []

        with self.assertRaises(frappe.ValidationError):
            settings.validate()

    def test_validation_with_incomplete_api_configuration(self):
        """Test validation when API configuration is missing required fields"""
        settings = frappe.get_single("Crosschex Settings")
        settings.enable_realtime_sync = 1
        settings.append("api_configurations", {
            "configuration_name": "Test Device",
            "api_url": "https://api.us.crosschexcloud.com/",
            # Missing api_key and api_secret
        })

        with self.assertRaises(frappe.ValidationError):
            settings.validate()