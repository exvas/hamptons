#!/usr/bin/env python3
"""
Test CrossChex sync for specific API configuration
Run with: bench --site hrms.hamptons.om execute hamptons.test_crosschex_sync.test_sync
"""

import frappe
import json


def test_sync():
    """Test sync for HAMTONS 3 configuration"""
    print("\n" + "="*80)
    print("Testing CrossChex Sync - HAMTONS 3 (API Key: 853cfe14ff50623d550056a72f829036)")
    print("="*80)
    
    # Get the API configuration
    config = frappe.db.get_value(
        "CrossChex API Configuration",
        {"api_key": "853cfe14ff50623d550056a72f829036"},
        ["name", "configuration_name", "api_url", "api_key", "connection_status", "last_sync_time"],
        as_dict=True
    )
    
    if not config:
        print("❌ Configuration not found!")
        return
    
    print(f"\n📋 Configuration Details:")
    print(f"  Name: {config['configuration_name']}")
    print(f"  API URL: {config['api_url']}")
    print(f"  API Key: {config['api_key']}")
    print(f"  Status: {config['connection_status']}")
    print(f"  Last Sync: {config['last_sync_time']}")
    
    # Check current checkin count
    before_count = frappe.db.count("Employee Checkin")
    print(f"\n📊 Current Stats:")
    print(f"  Total Employee Checkins: {before_count}")
    
    # Test the sync
    print(f"\n🔄 Running sync...")
    from hamptons.hamptons.doctype.crosschex_settings.crosschex_settings import sync_individual_device
    
    result = sync_individual_device(
        api_url=config['api_url'],
        api_key=config['api_key'],
        config_row_name=config['name'],
        config_name=config['configuration_name']
    )
    
    print(f"\n📝 Sync Result:")
    print(json.dumps(result, indent=2, default=str))
    
    # Check new checkin count
    after_count = frappe.db.count("Employee Checkin")
    new_checkins = after_count - before_count
    
    print(f"\n✅ Sync Complete:")
    print(f"  New Checkins Added: {new_checkins}")
    print(f"  Total Checkins Now: {after_count}")
    
    # Show recent checkins
    recent = frappe.db.sql("""
        SELECT employee, employee_name, time, log_type, device_id
        FROM `tabEmployee Checkin`
        ORDER BY time DESC
        LIMIT 5
    """, as_dict=True)
    
    print(f"\n📅 Most Recent Checkins:")
    for r in recent:
        print(f"  • {r['time']} - {r['employee_name']} ({r['employee']}) - {r['log_type']}")
    
    print("\n" + "="*80)
    print("Test Complete")
    print("="*80 + "\n")
    
    return result


if __name__ == "__main__":
    test_sync()
#!/usr/bin/env python3
"""
Test CrossChex sync for specific API configuration
Run with: bench --site hrms.hamptons.om execute hamptons.test_crosschex_sync.test_sync
"""

import frappe
import json


def test_sync():
    """Test sync for HAMTONS 3 configuration"""
    print("\n" + "="*80)
    print("Testing CrossChex Sync - HAMTONS 3 (API Key: 853cfe14ff50623d550056a72f829036)")
    print("="*80)
    
    # Get the API configuration
    config = frappe.db.get_value(
        "CrossChex API Configuration",
        {"api_key": "853cfe14ff50623d550056a72f829036"},
        ["name", "configuration_name", "api_url", "api_key", "connection_status", "last_sync_time"],
        as_dict=True
    )
    
    if not config:
        print("❌ Configuration not found!")
        return
    
    print(f"\n📋 Configuration Details:")
    print(f"  Name: {config['configuration_name']}")
    print(f"  API URL: {config['api_url']}")
    print(f"  API Key: {config['api_key']}")
    print(f"  Status: {config['connection_status']}")
    print(f"  Last Sync: {config['last_sync_time']}")
    
    # Check current checkin count
    before_count = frappe.db.count("Employee Checkin")
    print(f"\n📊 Current Stats:")
    print(f"  Total Employee Checkins: {before_count}")
    
    # Test the sync
    print(f"\n🔄 Running sync...")
    from hamptons.hamptons.doctype.crosschex_settings.crosschex_settings import sync_individual_device
    
    result = sync_individual_device(
        api_url=config['api_url'],
        api_key=config['api_key'],
        config_row_name=config['name'],
        config_name=config['configuration_name']
    )
    
    print(f"\n📝 Sync Result:")
    print(json.dumps(result, indent=2, default=str))
    
    # Check new checkin count
    after_count = frappe.db.count("Employee Checkin")
    new_checkins = after_count - before_count
    
    print(f"\n✅ Sync Complete:")
    print(f"  New Checkins Added: {new_checkins}")
    print(f"  Total Checkins Now: {after_count}")
    
    # Show recent checkins
    recent = frappe.db.sql("""
        SELECT employee, employee_name, time, log_type, device_id
        FROM `tabEmployee Checkin`
        ORDER BY time DESC
        LIMIT 5
    """, as_dict=True)
    
    print(f"\n📅 Most Recent Checkins:")
    for r in recent:
        print(f"  • {r['time']} - {r['employee_name']} ({r['employee']}) - {r['log_type']}")
    
    print("\n" + "="*80)
    print("Test Complete")
    print("="*80 + "\n")
    
    return result


if __name__ == "__main__":
    test_sync()
