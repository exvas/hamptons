import frappe
import unittest


class TestCrosschexSettings(unittest.TestCase):

    def test_crosschex_settings_creation(self):
        """Test that CrossChex Settings doctype can be created"""
        settings = frappe.get_single("Crosschex Settings")
        self.assertIsNotNone(settings)
    
    def test_validation_with_missing_credentials(self):
        """Test validation when sync is enabled but credentials are missing"""
        settings = frappe.get_single("Crosschex Settings")
        settings.enable_crosschex_sync = 1
        settings.api_key = ""
        settings.api_secret = ""
        
        with self.assertRaises(frappe.ValidationError):
            settings.validate()
    
    def test_token_generation_without_credentials(self):
        """Test token generation fails without credentials"""
        settings = frappe.get_single("Crosschex Settings")
        result = settings.generate_token()
        self.assertFalse(result.get("success"))