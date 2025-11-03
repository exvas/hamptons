#!/bin/bash

# Employee Check-in Dashboard Setup Script
# This script helps set up the Employee Check-in Dashboard in your Frappe site

echo "================================================"
echo "Employee Check-in Dashboard Setup"
echo "================================================"
echo ""

# Get site name
read -p "Enter your site name (e.g., hamptons.local): " SITE_NAME

if [ -z "$SITE_NAME" ]; then
    echo "Error: Site name is required"
    exit 1
fi

echo ""
echo "Setting up dashboard for site: $SITE_NAME"
echo ""

# Navigate to frappe-bench directory
BENCH_DIR="/home/frappe/frappe-bench"
if [ ! -d "$BENCH_DIR" ]; then
    echo "Error: Frappe bench directory not found at $BENCH_DIR"
    exit 1
fi

cd "$BENCH_DIR"

echo "Step 1: Running migrations..."
bench --site "$SITE_NAME" migrate

echo ""
echo "Step 2: Clearing cache..."
bench --site "$SITE_NAME" clear-cache

echo ""
echo "Step 3: Clearing website cache..."
bench --site "$SITE_NAME" clear-website-cache

echo ""
echo "Step 4: Building assets..."
bench build --app hamptons

echo ""
echo "Step 5: Restarting bench..."
bench restart

echo ""
echo "================================================"
echo "Setup Complete!"
echo "================================================"
echo ""
echo "Next Steps:"
echo "1. Login to your site: http://$SITE_NAME"
echo "2. Navigate to: Workspaces > Employee Check-in Dashboard"
echo "3. Or search for 'Employee Check-in Dashboard' in the search bar"
echo ""
echo "Features Available:"
echo "- Real-time attendance summary cards"
echo "- Interactive charts (Daily trends, Department-wise, Time distribution)"
echo "- Detailed Employee Check-in Report"
echo "- Quick access to related documents"
echo "- API endpoints for custom integrations"
echo ""
echo "For detailed documentation, see: DASHBOARD_README.md"
echo "================================================"
