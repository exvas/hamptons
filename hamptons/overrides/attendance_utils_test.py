import frappe
from frappe.utils import now_datetime, add_to_date
from hamptons.overrides.attendance_utils import get_first_in_last_out, infer_log_type_from_sequence

def test_get_first_in_last_out():
    """
    Comprehensive test for get_first_in_last_out function
    Covers various check-in scenarios with enhanced configuration options
    """
    base_time = now_datetime()
    test_cases = [
        # Scenario 1: Simple single check-in
        {
            'name': 'Single Checkin',
            'checkins': [
                {'name': 'check1', 'time': base_time, 'log_type': 'IN'}
            ],
            'config': {'min_checkins': 1},
            'expected_first_in': True,
            'expected_last_out': False
        },
        # Scenario 2: Multiple checkins with different log type inference strategies
        {
            'name': 'Time-Based Log Type Inference',
            'checkins': [
                {'name': 'check1', 'time': base_time, 'log_type': 'IN'},
                {'name': 'check2', 'time': add_to_date(base_time, minutes=45), 'log_type': 'IN'},
                {'name': 'check3', 'time': add_to_date(base_time, hours=2), 'log_type': 'IN'}
            ],
            'config': {
                'min_checkins': 3,
                'log_type_strategy': 'time_based',
                'max_break_hours': 5,
                'debug_logging': True
            },
            'expected_first_in': True,
            'expected_last_out': True,
            'use_inferred': True
        },
        # Scenario 3: OUT Time Detection Strategies
        {
            'name': 'Longest Duration OUT Time Strategy',
            'checkins': [
                {'name': 'check1', 'time': base_time, 'log_type': 'IN'},
                {'name': 'check2', 'time': add_to_date(base_time, hours=2), 'log_type': 'OUT'},
                {'name': 'check3', 'time': add_to_date(base_time, hours=4), 'log_type': 'OUT'}
            ],
            'config': {
                'min_checkins': 3,
                'out_time_strategy': 'longest_duration',
                'max_break_hours': 5
            },
            'expected_first_in': True,
            'expected_last_out': True,
            'use_inferred': True,
            'validate_longest_duration': True
        },
        # Scenario 4: Overnight shift with complex log type inference
        {
            'name': 'Overnight Shift with Time-Based Inference',
            'checkins': [
                {'name': 'check1', 'time': base_time, 'log_type': 'IN'},
                {'name': 'check2', 'time': add_to_date(base_time, hours=8), 'log_type': 'IN'},
                {'name': 'check3', 'time': add_to_date(base_time, days=1), 'log_type': 'OUT'}
            ],
            'config': {
                'allow_overnight_shifts': True,
                'max_break_hours': 24,
                'log_type_strategy': 'time_based',
                'out_time_strategy': 'last_out'
            },
            'expected_first_in': True,
            'expected_last_out': True
        },
        # Scenario 5: Strict log type validation with debug logging
        {
            'name': 'Strict Log Type with Debug',
            'checkins': [
                {'name': 'check1', 'time': base_time, 'log_type': 'OUT'},
                {'name': 'check2', 'time': add_to_date(base_time, hours=2), 'log_type': 'IN'}
            ],
            'config': {
                'strict_log_type': True,
                'min_checkins': 2,
                'debug_logging': True
            },
            'expected_first_in': False,
            'expected_last_out': False
        }
    ]

    for case in test_cases:
        print(f"Running test case: {case['name']}")
        
        use_inferred = case.get('use_inferred', False)
        config = case.get('config', {})
        
        first_in, last_out = get_first_in_last_out(case['checkins'], use_inferred=use_inferred, config=config)
        
        # Validate first IN
        assert (first_in is not None) == case['expected_first_in'], \
            f"Failed to detect first IN for {case['name']}"
        
        # Validate last OUT
        assert (last_out is not None) == case['expected_last_out'], \
            f"Failed to detect last OUT for {case['name']}"
        
        # Additional validation for longest duration strategy
        if case.get('validate_longest_duration', False):
            # Verify that the last_out is the check-in with the longest duration from first IN
            assert last_out['name'] == 'check3', \
                f"Failed to select longest duration OUT time for {case['name']}"
        
        print(f"Test case {case['name']} passed successfully.")

def test_infer_log_type_from_sequence():
    """
    Test log type inference for devices marking all checkins as 'IN'
    """
    test_checkins = [
        {'name': 'check1', 'time': now_datetime(), 'log_type': 'IN'},
        {'name': 'check2', 'time': add_to_date(now_datetime(), hours=2), 'log_type': 'IN'},
        {'name': 'check3', 'time': add_to_date(now_datetime(), hours=4), 'log_type': 'IN'}
    ]
    
    inferred_checkins = infer_log_type_from_sequence(test_checkins)
    
    expected_log_types = ['IN', 'OUT', 'IN']
    for i, checkin in enumerate(inferred_checkins):
        assert checkin['inferred_log_type'] == expected_log_types[i], \
            f"Incorrect log type inference for checkin {i}"
    
    print("Log type inference test passed successfully.")

def run_attendance_utils_tests():
    """
    Run all tests for attendance utils
    """
    try:
        test_get_first_in_last_out()
        test_infer_log_type_from_sequence()
        print("All Attendance Utils Tests Passed Successfully!")
    except AssertionError as e:
        print(f"Test Failed: {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected Error in Tests: {str(e)}")
        raise

# Uncomment to run tests directly
# run_attendance_utils_tests()