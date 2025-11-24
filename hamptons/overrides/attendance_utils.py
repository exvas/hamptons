# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, get_datetime
from datetime import datetime, timedelta


def infer_log_type_from_sequence(checkins):
	"""
	Infer IN/OUT log types based on time sequence.
	Assumes alternating pattern: first = IN, second = OUT, third = IN, fourth = OUT, etc.

	This is necessary because many biometric devices mark all checkins as "IN".

	Args:
		checkins: List of checkin dicts with 'time' field (sorted by time)

	Returns:
		List of checkin dicts with inferred 'inferred_log_type' field
	"""
	if not checkins:
		return []

	result = []
	for idx, checkin in enumerate(checkins):
		# Create a copy to avoid modifying original
		checkin_copy = checkin.copy()

		# Alternate between IN and OUT based on sequence
		# First checkin (index 0) = IN
		# Second checkin (index 1) = OUT
		# Third checkin (index 2) = IN
		# Fourth checkin (index 3) = OUT
		# etc.
		checkin_copy['inferred_log_type'] = 'IN' if idx % 2 == 0 else 'OUT'
		checkin_copy['original_log_type'] = checkin.get('log_type', 'IN')

		result.append(checkin_copy)

	return result


def get_first_in_last_out(checkins, use_inferred=True):
	"""
	Get first IN and last OUT checkins from a list of checkins.

	Args:
		checkins: List of checkin dicts (sorted by time)
		use_inferred: If True, use inferred_log_type; if False, use log_type

	Returns:
		tuple: (first_in, last_out) checkin dicts or None
	"""
	if not checkins:
		return None, None

	# Infer log types if requested
	if use_inferred:
		checkins = infer_log_type_from_sequence(checkins)
		log_type_field = 'inferred_log_type'
	else:
		log_type_field = 'log_type'

	# Find first IN
	first_in = None
	for checkin in checkins:
		if checkin.get(log_type_field) == 'IN':
			first_in = checkin
			break

	# Find last OUT
	last_out = None
	for checkin in reversed(checkins):
		if checkin.get(log_type_field) == 'OUT':
			last_out = checkin
			break

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

		first_in_dt = get_datetime(first_in_time) if not isinstance(first_in_time, datetime) else first_in_time

		if first_in_dt > shift_start_dt:
			needs_regularization = True
			diff = first_in_dt - shift_start_dt
			hours = int(diff.total_seconds() // 3600)
			minutes = int((diff.total_seconds() % 3600) // 60)
			seconds = int(diff.total_seconds() % 60)
			late_time = get_time(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

	# Check early exit
	if last_out_time:
		shift_end_dt = datetime.combine(processing_date, end_time)
		last_out_dt = get_datetime(last_out_time) if not isinstance(last_out_time, datetime) else last_out_time

		if last_out_dt < shift_end_dt:
			needs_regularization = True
			diff = shift_end_dt - last_out_dt
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
