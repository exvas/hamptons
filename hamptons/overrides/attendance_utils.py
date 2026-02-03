# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, get_datetime
from datetime import datetime, timedelta


def infer_log_type_from_sequence(checkins, strategy='alternating'):
    """
    Enhanced log type inference with multiple strategies for detecting IN/OUT check-ins.

    Args:
        checkins (list): List of check-in dictionaries, sorted by time
        strategy (str): Log type inference strategy:
            - 'alternating': Default, alternates IN/OUT
            - 'time_based': Infer based on time gaps between check-ins
            - 'location_based': Use location changes to detect IN/OUT (if location data available)
            - 'duration_based': Use check-in duration to determine log type

    Returns:
        List of check-in dictionaries with inferred log types
    """
    if not checkins:
        return []

    # Default to alternating strategy if unsupported strategy provided
    if strategy not in ['alternating', 'time_based', 'location_based', 'duration_based']:
        strategy = 'alternating'

    result = []
    
    if strategy == 'alternating':
        # Original alternating strategy
        for idx, checkin in enumerate(checkins):
            checkin_copy = checkin.copy()
            checkin_copy['inferred_log_type'] = 'IN' if idx % 2 == 0 else 'OUT'
            checkin_copy['original_log_type'] = checkin.get('log_type', 'IN')
            result.append(checkin_copy)
    
    elif strategy == 'time_based':
        # Time-based log type inference
        for idx, checkin in enumerate(checkins):
            checkin_copy = checkin.copy()
            
            # First check-in is always IN
            if idx == 0:
                checkin_copy['inferred_log_type'] = 'IN'
            else:
                prev_checkin = checkins[idx-1]
                current_time = get_datetime(checkin['time'])
                prev_time = get_datetime(prev_checkin['time'])
                
                # Calculate time gap
                time_gap = (current_time - prev_time).total_seconds() / 60  # minutes
                
                # Heuristics for log type inference
                if time_gap > 30:  # More than 30 minutes gap suggests potential OUT/IN
                    checkin_copy['inferred_log_type'] = 'OUT' if prev_checkin.get('inferred_log_type', 'IN') == 'IN' else 'IN'
                else:
                    # Short time gap, continue with previous log type pattern
                    checkin_copy['inferred_log_type'] = 'OUT' if prev_checkin.get('inferred_log_type', 'IN') == 'IN' else 'IN'
            
            checkin_copy['original_log_type'] = checkin.get('log_type', 'IN')
            result.append(checkin_copy)
    
    elif strategy == 'duration_based':
        # Duration-based log type inference (requires more context about shift timings)
        for idx, checkin in enumerate(checkins):
            checkin_copy = checkin.copy()
            
            # Placeholder for more complex duration-based logic
            # Would require access to shift timing, standard working hours
            checkin_copy['inferred_log_type'] = 'IN' if idx % 2 == 0 else 'OUT'
            checkin_copy['original_log_type'] = checkin.get('log_type', 'IN')
            result.append(checkin_copy)
    
    elif strategy == 'location_based':
        # Location-based log type inference (if location data is available)
        for idx, checkin in enumerate(checkins):
            checkin_copy = checkin.copy()
            
            # Requires location data in check-in record
            if 'location' in checkin:
                # Placeholder for location-based logic
                # Would compare location changes to infer IN/OUT
                checkin_copy['inferred_log_type'] = 'IN' if idx % 2 == 0 else 'OUT'
            else:
                # Fallback to alternating if no location data
                checkin_copy['inferred_log_type'] = 'IN' if idx % 2 == 0 else 'OUT'
            
            checkin_copy['original_log_type'] = checkin.get('log_type', 'IN')
            result.append(checkin_copy)
    
    return result


def get_first_in_last_out(checkins, use_inferred=True, config=None):
    """
    Get first IN and last OUT checkins from a list of checkins with enhanced configuration.

    Args:
        checkins: List of checkin dicts (sorted by time)
        use_inferred: If True, use inferred_log_type; if False, use log_type
        config: Optional configuration dictionary with additional parameters
            - min_checkins: Minimum number of checkins required for valid attendance
            - max_break_hours: Maximum allowed break between checkins
            - strict_log_type: Enforce strict IN/OUT log type matching
            - log_type_strategy: Strategy for log type inference
                ('alternating', 'time_based', 'location_based', 'duration_based', 'simple')
            - out_time_strategy: Method for determining final OUT time
                ('last_out', 'longest_duration', 'shift_end_aligned')
            - debug_logging: Enable detailed debug logging

    Returns:
        tuple: (first_in, last_out) checkin dicts or None

    Raises:
        ValueError for configuration or data validation errors
    """
    # Default configuration with expanded options
    default_config = {
        'min_checkins': 1,  # Minimum checkins for valid attendance
        'max_break_hours': 12,  # Maximum allowed break between checkins
        'strict_log_type': False,  # Enforce strict log type matching
        'allow_overnight_shifts': True,  # Allow shifts crossing midnight
        'log_type_strategy': 'simple',  # Changed to 'simple' for first=IN, last=OUT
        'out_time_strategy': 'last_out',  # Strategy for determining OUT time
        'debug_logging': False,  # Enable detailed debug logging
    }

    # Merge provided config with default
    config = {**default_config, **(config or {})}

    if not checkins:
        return None, None

    # Validate minimum checkins
    if len(checkins) < config['min_checkins']:
        if config['debug_logging']:
            frappe.logger().warning(f"Insufficient checkins: {len(checkins)} < {config['min_checkins']}")
        return None, None

    # SIMPLE STRATEGY: First checkin = IN, Last checkin = OUT
    if config['log_type_strategy'] == 'simple':
        # Copy checkins and mark first as IN, last as OUT
        checkins_copy = []
        for idx, checkin in enumerate(checkins):
            checkin_copy = checkin.copy()
            if idx == 0:
                checkin_copy['inferred_log_type'] = 'IN'
            elif idx == len(checkins) - 1:
                checkin_copy['inferred_log_type'] = 'OUT'
            else:
                # Middle checkins keep their original type or alternate
                checkin_copy['inferred_log_type'] = checkin.get('log_type', 'IN')
            checkin_copy['original_log_type'] = checkin.get('log_type', 'IN')
            checkins_copy.append(checkin_copy)

        checkins = checkins_copy
        log_type_field = 'inferred_log_type'

        # Handle single checkin case based on its actual log_type
        if len(checkins) == 1:
            single_checkin = checkins[0]
            original_type = single_checkin.get('original_log_type', 'IN')
            if original_type == 'OUT':
                # Single OUT checkin: no check-in, only check-out
                first_in = None
                last_out = single_checkin
            else:
                # Single IN checkin (or unknown): check-in only, no check-out
                first_in = single_checkin
                last_out = None
        else:
            # Multiple checkins: first = IN, last = OUT
            first_in = checkins[0] if len(checkins) > 0 else None
            last_out = checkins[-1] if len(checkins) > 1 else None
    else:
        # Infer log types using the specified strategy
        if use_inferred:
            checkins = infer_log_type_from_sequence(
                checkins,
                strategy=config['log_type_strategy']
            )
            log_type_field = 'inferred_log_type'
        else:
            log_type_field = 'log_type'

        # Find first IN checkin
        first_in = next(
            (checkin for checkin in checkins if checkin.get(log_type_field) == 'IN'),
            None
        )

        # Advanced OUT time determination
        if config['out_time_strategy'] == 'last_out':
            # Default behavior: find last OUT checkin
            last_out = next(
                (checkin for checkin in reversed(checkins) if checkin.get(log_type_field) == 'OUT'),
                None
            )
        elif config['out_time_strategy'] == 'longest_duration':
            # Find OUT checkin that creates the longest working duration
            last_out = None
            if first_in:
                first_in_time = get_datetime(first_in['time'])
                max_duration = timedelta()
                for checkin in checkins:
                    if checkin.get(log_type_field) == 'OUT':
                        out_time = get_datetime(checkin['time'])
                        duration = out_time - first_in_time
                        if duration > max_duration:
                            max_duration = duration
                            last_out = checkin
        elif config['out_time_strategy'] == 'shift_end_aligned':
            # TODO: Implement shift-end aligned OUT time detection
            # This would require additional context about shift timings
            last_out = next(
                (checkin for checkin in reversed(checkins) if checkin.get(log_type_field) == 'OUT'),
                None
            )
        else:
            # Fallback to default last OUT
            last_out = next(
                (checkin for checkin in reversed(checkins) if checkin.get(log_type_field) == 'OUT'),
                None
            )

    # Strict log type validation
    if config['strict_log_type']:
        if first_in and first_in.get('log_type') != 'IN':
            if config['debug_logging']:
                frappe.logger().warning(f"Strict log type validation failed for first IN: {first_in.get('log_type')}")
            first_in = None
        if last_out and last_out.get('log_type') != 'OUT':
            if config['debug_logging']:
                frappe.logger().warning(f"Strict log type validation failed for last OUT: {last_out.get('log_type')}")
            last_out = None

    # Break duration validation
    if first_in and last_out:
        first_in_time = get_datetime(first_in['time'])
        last_out_time = get_datetime(last_out['time'])
        
        break_hours = (last_out_time - first_in_time).total_seconds() / 3600
        
        if break_hours > config['max_break_hours'] and not config['allow_overnight_shifts']:
            if config['debug_logging']:
                frappe.logger().warning(f"Break duration exceeded: {break_hours} hours")
            return None, None

    # Detailed logging for complex scenarios
    if config['debug_logging'] and first_in and last_out:
        frappe.logger().info(
            f"Attendance Consolidation: "
            f"First IN at {first_in['time']} (Strategy: {config['log_type_strategy']}), "
            f"Last OUT at {last_out['time']} (Strategy: {config['out_time_strategy']})"
        )

    return first_in, last_out


def calculate_late_early_times(first_in_time, last_out_time, shift_type, processing_date):
	"""
	Calculate late entry and early exit times based on shift timings.

	Args:
		first_in_time: datetime of first IN checkin (or None)
		last_out_time: datetime of last OUT checkin (or None)
		shift_type: Shift Type document
		processing_date: Date being processed

	Returns:
		dict: {
			'late_time': time object or None,
			'early_exit_time': time object or None,
			'needs_regularization': bool
		}
	"""
	from frappe.utils import get_time
	from datetime import time as dt_time

	late_time = None
	early_exit_time = None
	needs_regularization = False

	# Handle shift start time (convert timedelta to time if needed)
	start_time = shift_type.start_time
	if isinstance(start_time, timedelta):
		total_seconds = int(start_time.total_seconds())
		hours = total_seconds // 3600
		minutes = (total_seconds % 3600) // 60
		seconds = total_seconds % 60
		start_time = get_time(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
	elif not isinstance(start_time, dt_time):
		start_time = get_time(start_time)

	# Handle shift end time (convert timedelta to time if needed)
	end_time = shift_type.end_time
	if isinstance(end_time, timedelta):
		total_seconds = int(end_time.total_seconds())
		hours = total_seconds // 3600
		minutes = (total_seconds % 3600) // 60
		seconds = total_seconds % 60
		end_time = get_time(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
	elif not isinstance(end_time, dt_time):
		end_time = get_time(end_time)

	# Check late entry
	if first_in_time:
		grace = int(getattr(shift_type, "late_entry_grace_period", 0) or 0)
		shift_start_dt = datetime.combine(processing_date, start_time)
		shift_start_dt += timedelta(minutes=grace)

		# FIXED: Ensure first_in_time is properly converted to datetime
		# If first_in_time is a time object without date, combine it with processing_date
		if isinstance(first_in_time, dt_time):
			first_in_dt = datetime.combine(processing_date, first_in_time)
		elif not isinstance(first_in_time, datetime):
			first_in_dt = get_datetime(first_in_time)
		else:
			first_in_dt = first_in_time

		# Only calculate late time if employee actually arrived late
		if first_in_dt > shift_start_dt:
			needs_regularization = True
			diff = first_in_dt - shift_start_dt
			# Safety check: only create late_time if diff is positive
			if diff.total_seconds() > 0:
				hours = int(diff.total_seconds() // 3600)
				minutes = int((diff.total_seconds() % 3600) // 60)
				seconds = int(diff.total_seconds() % 60)
				late_time = get_time(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

	# Check early exit
	if last_out_time:
		# Apply early exit grace period (if configured in shift type)
		early_grace = int(getattr(shift_type, "early_exit_grace_period", 0) or 0)
		shift_end_dt = datetime.combine(processing_date, end_time)
		shift_end_with_grace = shift_end_dt - timedelta(minutes=early_grace)

		# FIXED: Ensure last_out_time is properly converted to datetime
		# If last_out_time is a time object without date, combine it with processing_date
		if isinstance(last_out_time, dt_time):
			last_out_dt = datetime.combine(processing_date, last_out_time)
		elif not isinstance(last_out_time, datetime):
			last_out_dt = get_datetime(last_out_time)
		else:
			last_out_dt = last_out_time

		# Only calculate early exit time if employee left before shift end minus grace period
		if last_out_dt < shift_end_with_grace:
			needs_regularization = True
			diff = shift_end_with_grace - last_out_dt
			# Safety check: only create early_exit_time if diff is positive
			if diff.total_seconds() > 0:
				hours = int(diff.total_seconds() // 3600)
				minutes = int((diff.total_seconds() % 3600) // 60)
				seconds = int(diff.total_seconds() % 60)
				early_exit_time = get_time(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

	# If missing IN or OUT, needs regularization
	if not first_in_time or not last_out_time:
		needs_regularization = True

	return {
		'late_time': late_time,
		'early_exit_time': early_exit_time,
		'needs_regularization': needs_regularization
	}
