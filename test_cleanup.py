#!/usr/bin/env python3
"""
Test script for cleanup functionality
Run with: bench --site [site-name] execute hamptons.test_cleanup.test_cleanup
"""

import frappe
from hamptons.utils import cleanup_old_logs, manual_cleanup


def test_cleanup():
    """Test the cleanup function"""
    print("\n" + "="*60)
    print("Testing Cleanup Functionality")
    print("="*60)
    
    # Get current counts
    error_log_count = frappe.db.count("Error Log")
    deleted_doc_count = frappe.db.count("Deleted Document")
    
    print(f"\nCurrent counts:")
    print(f"  Error Logs: {error_log_count}")
    print(f"  Deleted Documents: {deleted_doc_count}")
    
    # Run cleanup
    print("\nRunning cleanup...")
    result = cleanup_old_logs()
    
    if result.get("success"):
        print(f"\n✓ Cleanup completed successfully!")
        print(f"  Error logs deleted: {result['error_logs_deleted']}")
        print(f"  Deleted documents removed: {result['deleted_documents_removed']}")
        print(f"  Cutoff date: {result['cutoff_date']}")
    else:
        print(f"\n✗ Cleanup failed: {result.get('error')}")
    
    # Get new counts
    new_error_log_count = frappe.db.count("Error Log")
    new_deleted_doc_count = frappe.db.count("Deleted Document")
    
    print(f"\nNew counts:")
    print(f"  Error Logs: {new_error_log_count}")
    print(f"  Deleted Documents: {new_deleted_doc_count}")
    
    print("\n" + "="*60)
    print("Test Complete")
    print("="*60 + "\n")
    
    return result


if __name__ == "__main__":
    test_cleanup()
