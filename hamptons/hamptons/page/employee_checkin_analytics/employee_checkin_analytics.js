// Copyright (c) 2024, Momscode and contributors
// For license information, please see license.txt

frappe.pages['employee-checkin-analytics'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Employee Check-in Analytics',
		single_column: true
	});

	// Wait for page to be ready
	setTimeout(() => {
		// Add custom styling
		if (page.$page && page.$page.find) {
			page.$page.find('.page-head').css({
				'background': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
				'color': 'white',
				'border-radius': '8px',
				'margin-bottom': '20px',
				'padding': '15px'
			});
		}

		new EmployeeCheckinAnalytics(page);
	}, 100);
};

class EmployeeCheckinAnalytics {
	constructor(page) {
		this.page = page;
		this.parent = $(this.page.body);
		this.filters = {};
		this.charts = {};
		
		this.make_filters();
		this.make_dashboard();
		this.load_data();
	}

	make_filters() {
		// Filter section
		const filter_html = `
			<div class="filter-section" style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
				<div class="row">
					<div class="col-sm-3">
						<label class="control-label" style="font-weight: 600;">From Date</label>
						<input type="date" class="form-control" id="from_date" value="${frappe.datetime.add_days(frappe.datetime.nowdate(), -30)}">
					</div>
					<div class="col-sm-3">
						<label class="control-label" style="font-weight: 600;">To Date</label>
						<input type="date" class="form-control" id="to_date" value="${frappe.datetime.nowdate()}">
					</div>
					<div class="col-sm-3">
						<label class="control-label" style="font-weight: 600;">Employee</label>
						<div id="employee_filter"></div>
					</div>
					<div class="col-sm-3">
						<label class="control-label" style="font-weight: 600;">Department</label>
						<div id="department_filter"></div>
					</div>
				</div>
				<div class="row" style="margin-top: 15px;">
					<div class="col-sm-12">
						<button class="btn btn-primary btn-sm" id="apply_filters">
							<i class="fa fa-filter"></i> Apply Filters
						</button>
						<button class="btn btn-default btn-sm" id="reset_filters">
							<i class="fa fa-refresh"></i> Reset
						</button>
						<button class="btn btn-success btn-sm pull-right" id="export_data">
							<i class="fa fa-download"></i> Export to Excel
						</button>
					</div>
				</div>
			</div>
		`;
		
		this.parent.append(filter_html);

		// Employee filter
		this.employee_field = frappe.ui.form.make_control({
			parent: this.parent.find('#employee_filter'),
			df: {
				fieldtype: 'Link',
				options: 'Employee',
				placeholder: 'All Employees'
			},
			render_input: true
		});

		// Department filter
		this.department_field = frappe.ui.form.make_control({
			parent: this.parent.find('#department_filter'),
			df: {
				fieldtype: 'Link',
				options: 'Department',
				placeholder: 'All Departments'
			},
			render_input: true
		});

		// Filter button events
		this.parent.find('#apply_filters').on('click', () => this.load_data());
		this.parent.find('#reset_filters').on('click', () => this.reset_filters());
		this.parent.find('#export_data').on('click', () => this.export_to_excel());
	}

	make_dashboard() {
		const dashboard_html = `
			<div class="analytics-dashboard">
				<!-- Summary Cards -->
				<div class="row summary-cards" style="margin-bottom: 20px;">
					<div class="col-sm-3">
						<div class="summary-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
							<div style="font-size: 14px; opacity: 0.9; margin-bottom: 5px;">Total Check-ins</div>
							<div style="font-size: 32px; font-weight: bold;" id="total_checkins">0</div>
							<div style="font-size: 12px; opacity: 0.8; margin-top: 5px;">
								<i class="fa fa-arrow-up"></i> <span id="checkins_change">0%</span> from last period
							</div>
						</div>
					</div>
					<div class="col-sm-3">
						<div class="summary-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
							<div style="font-size: 14px; opacity: 0.9; margin-bottom: 5px;">Unique Employees</div>
							<div style="font-size: 32px; font-weight: bold;" id="unique_employees">0</div>
							<div style="font-size: 12px; opacity: 0.8; margin-top: 5px;">
								<i class="fa fa-users"></i> Active employees
							</div>
						</div>
					</div>
					<div class="col-sm-3">
						<div class="summary-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
							<div style="font-size: 14px; opacity: 0.9; margin-bottom: 5px;">Avg Daily Check-ins</div>
							<div style="font-size: 32px; font-weight: bold;" id="avg_daily">0</div>
							<div style="font-size: 12px; opacity: 0.8; margin-top: 5px;">
								<i class="fa fa-calendar"></i> Per day average
							</div>
						</div>
					</div>
					<div class="col-sm-3">
						<div class="summary-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
							<div style="font-size: 14px; opacity: 0.9; margin-bottom: 5px;">Devices Used</div>
							<div style="font-size: 32px; font-weight: bold;" id="total_devices">0</div>
							<div style="font-size: 12px; opacity: 0.8; margin-top: 5px;">
								<i class="fa fa-mobile"></i> Unique devices
							</div>
						</div>
					</div>
				</div>

				<!-- Charts Row 1 -->
				<div class="row" style="margin-bottom: 20px;">
					<div class="col-sm-8">
						<div class="chart-card" style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
							<h4 style="margin-bottom: 15px; color: #333;">
								<i class="fa fa-line-chart"></i> Daily Check-in Trend
							</h4>
							<div id="daily_trend_chart"></div>
						</div>
					</div>
					<div class="col-sm-4">
						<div class="chart-card" style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
							<h4 style="margin-bottom: 15px; color: #333;">
								<i class="fa fa-pie-chart"></i> Check-in Type
							</h4>
							<div id="checkin_type_chart"></div>
						</div>
					</div>
				</div>

				<!-- Charts Row 2 -->
				<div class="row" style="margin-bottom: 20px;">
					<div class="col-sm-6">
						<div class="chart-card" style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
							<h4 style="margin-bottom: 15px; color: #333;">
								<i class="fa fa-clock-o"></i> Hourly Distribution
							</h4>
							<div id="hourly_distribution_chart"></div>
						</div>
					</div>
					<div class="col-sm-6">
						<div class="chart-card" style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
							<h4 style="margin-bottom: 15px; color: #333;">
								<i class="fa fa-building"></i> Department-wise Check-ins
							</h4>
							<div id="department_chart"></div>
						</div>
					</div>
				</div>

				<!-- Top Employees Table -->
				<div class="row" style="margin-bottom: 20px;">
					<div class="col-sm-12">
						<div class="chart-card" style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
							<h4 style="margin-bottom: 15px; color: #333;">
								<i class="fa fa-trophy"></i> Top Active Employees
							</h4>
							<div id="top_employees_table"></div>
						</div>
					</div>
				</div>

				<!-- Device Usage -->
				<div class="row">
					<div class="col-sm-12">
						<div class="chart-card" style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
							<h4 style="margin-bottom: 15px; color: #333;">
								<i class="fa fa-mobile"></i> Device Usage Statistics
							</h4>
							<div id="device_usage_chart"></div>
						</div>
					</div>
				</div>
			</div>
		`;
		
		this.parent.append(dashboard_html);
	}

	get_filters() {
		return {
			from_date: this.parent.find('#from_date').val(),
			to_date: this.parent.find('#to_date').val(),
			employee: this.employee_field.get_value(),
			department: this.department_field.get_value()
		};
	}

	reset_filters() {
		this.parent.find('#from_date').val(frappe.datetime.add_days(frappe.datetime.nowdate(), -30));
		this.parent.find('#to_date').val(frappe.datetime.nowdate());
		this.employee_field.set_value('');
		this.department_field.set_value('');
		this.load_data();
	}

	load_data() {
		frappe.dom.freeze('Loading analytics...');
		
		const filters = this.get_filters();

		frappe.call({
			method: 'hamptons.hamptons.page.employee_checkin_analytics.employee_checkin_analytics.get_analytics_data',
			args: { filters: filters },
			callback: (r) => {
				frappe.dom.unfreeze();
				if (r.message) {
					this.render_dashboard(r.message);
				}
			}
		});
	}

	render_dashboard(data) {
		// Update summary cards
		this.parent.find('#total_checkins').text(data.summary.total_checkins || 0);
		this.parent.find('#unique_employees').text(data.summary.unique_employees || 0);
		this.parent.find('#avg_daily').text(data.summary.avg_daily_checkins || 0);
		this.parent.find('#total_devices').text(data.summary.total_devices || 0);
		this.parent.find('#checkins_change').text((data.summary.change_percentage || 0) + '%');

		// Render charts
		this.render_daily_trend(data.daily_trend);
		this.render_checkin_type(data.checkin_type);
		this.render_hourly_distribution(data.hourly_distribution);
		this.render_department_chart(data.department_wise);
		this.render_top_employees(data.top_employees);
		this.render_device_usage(data.device_usage);
	}

	render_daily_trend(data) {
		const container = this.parent.find('#daily_trend_chart');
		if (!container.length) return;
		
		if (!data || data.length === 0) {
			container.html('<p class="text-muted text-center" style="padding: 40px;">No data available</p>');
			return;
		}

		try {
			const chart = new frappe.Chart(container[0], {
				data: {
					labels: data.map(d => d.date),
					datasets: [
						{
							name: 'Check-ins',
							values: data.map(d => d.count)
						}
					]
				},
				type: 'line',
				height: 250,
				colors: ['#667eea'],
				lineOptions: {
					regionFill: 1,
					hideDots: 0
				}
			});

			this.charts.daily_trend = chart;
		} catch (error) {
			console.error('Error rendering daily trend chart:', error);
			container.html('<p class="text-muted text-center">Error loading chart</p>');
		}
	}

	render_checkin_type(data) {
		const container = this.parent.find('#checkin_type_chart');
		if (!container.length) return;
		
		if (!data || data.length === 0) {
			container.html('<p class="text-muted text-center" style="padding: 40px;">No data available</p>');
			return;
		}

		try {
			const chart = new frappe.Chart(container[0], {
				data: {
					labels: data.map(d => d.log_type || 'Unknown'),
					datasets: [{
						values: data.map(d => d.count)
					}]
				},
				type: 'pie',
				height: 230,
				colors: ['#43e97b', '#f5576c']
			});

			this.charts.checkin_type = chart;
		} catch (error) {
			console.error('Error rendering checkin type chart:', error);
			container.html('<p class="text-muted text-center">Error loading chart</p>');
		}
	}

	render_hourly_distribution(data) {
		const container = this.parent.find('#hourly_distribution_chart');
		if (!container.length) return;
		
		if (!data || data.length === 0) {
			container.html('<p class="text-muted text-center" style="padding: 40px;">No data available</p>');
			return;
		}

		try {
			const chart = new frappe.Chart(container[0], {
				data: {
					labels: data.map(d => (d.hour || 0) + ':00'),
					datasets: [{
						name: 'Check-ins',
						values: data.map(d => d.count)
					}]
				},
				type: 'bar',
				height: 250,
				colors: ['#4facfe'],
				barOptions: {
					spaceRatio: 0.5
				}
			});

			this.charts.hourly = chart;
		} catch (error) {
			console.error('Error rendering hourly chart:', error);
			container.html('<p class="text-muted text-center">Error loading chart</p>');
		}
	}

	render_department_chart(data) {
		const container = this.parent.find('#department_chart');
		if (!container.length) return;
		
		if (!data || data.length === 0) {
			container.html('<p class="text-muted text-center" style="padding: 40px;">No data available</p>');
			return;
		}

		try {
			const chart = new frappe.Chart(container[0], {
				data: {
					labels: data.map(d => d.department || 'Unassigned'),
					datasets: [{
						values: data.map(d => d.count)
					}]
				},
				type: 'percentage',
				height: 250,
				colors: ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#43e97b']
			});

			this.charts.department = chart;
		} catch (error) {
			console.error('Error rendering department chart:', error);
			container.html('<p class="text-muted text-center">Error loading chart</p>');
		}
	}

	render_top_employees(data) {
		if (!data || data.length === 0) {
			this.parent.find('#top_employees_table').html('<p class="text-muted text-center">No data available</p>');
			return;
		}

		let html = `
			<table class="table table-bordered table-hover">
				<thead style="background: #f5f7fa;">
					<tr>
						<th width="5%">#</th>
						<th width="30%">Employee</th>
						<th width="20%">Department</th>
						<th width="15%">Check-ins</th>
						<th width="15%">Check-outs</th>
						<th width="15%">Total</th>
					</tr>
				</thead>
				<tbody>
		`;

		data.forEach((emp, idx) => {
			html += `
				<tr>
					<td>${idx + 1}</td>
					<td>
						<strong>${emp.employee_name}</strong><br>
						<small class="text-muted">${emp.employee}</small>
					</td>
					<td>${emp.department || '-'}</td>
					<td><span class="badge" style="background: #43e97b;">${emp.check_ins}</span></td>
					<td><span class="badge" style="background: #f5576c;">${emp.check_outs}</span></td>
					<td><strong>${emp.total}</strong></td>
				</tr>
			`;
		});

		html += '</tbody></table>';
		this.parent.find('#top_employees_table').html(html);
	}

	render_device_usage(data) {
		const container = this.parent.find('#device_usage_chart');
		if (!container.length) return;
		
		if (!data || data.length === 0) {
			container.html('<p class="text-muted text-center" style="padding: 40px;">No data available</p>');
			return;
		}

		try {
			const chart = new frappe.Chart(container[0], {
				data: {
					labels: data.map(d => d.device_id || 'Unknown'),
					datasets: [{
						name: 'Usage Count',
						values: data.map(d => d.count)
					}]
				},
				type: 'bar',
				height: 250,
				colors: ['#f093fb'],
				barOptions: {
					spaceRatio: 0.3
				}
			});

			this.charts.device = chart;
		} catch (error) {
			console.error('Error rendering device chart:', error);
			container.html('<p class="text-muted text-center">Error loading chart</p>');
		}
	}

	export_to_excel() {
		const filters = this.get_filters();
		
		frappe.call({
			method: 'hamptons.hamptons.page.employee_checkin_analytics.employee_checkin_analytics.export_to_excel',
			args: { filters: filters },
			callback: (r) => {
				if (r.message) {
					window.open(r.message.file_url);
				}
			}
		});
	}
}
