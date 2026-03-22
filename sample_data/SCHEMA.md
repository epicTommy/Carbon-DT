# Sample Data Schema Notes

These files are placeholders for MVP development and local demos. Values are illustrative, not production-grade.

## `buildings.csv`

- `building_id`: unique identifier for a building or site
- `building_name`: human-readable building name
- `address`: site address
- `building_type`: office, school, warehouse, etc.
- `floor_area_sqft`: gross floor area in square feet
- `year_built`: year originally constructed

## `utility_bills.csv`

- `bill_id`: unique utility bill identifier
- `building_id`: foreign key to `buildings.csv`
- `meter_type`: electricity, gas, water, etc.
- `billing_period_start`: billing period start date
- `billing_period_end`: billing period end date
- `usage`: billed consumption for the period
- `cost_usd`: billed cost in USD

## `equipment_inventory.csv`

- `equipment_id`: unique equipment identifier
- `building_id`: foreign key to `buildings.csv`
- `system_type`: HVAC, lighting, envelope, controls, etc.
- `equipment_name`: descriptive equipment label
- `quantity`: installed quantity
- `status`: active, planned replacement, unknown

## `audit_measures.csv`

- `measure_id`: unique energy conservation measure identifier
- `building_id`: foreign key to `buildings.csv`
- `measure_name`: short measure label
- `category`: controls, lighting, HVAC, envelope, operations
- `estimated_savings_kwh`: estimated annual electric savings
- `estimated_cost_usd`: implementation cost estimate
- `status`: backlog, evaluated, selected, rejected

## `monthly_weather.csv`

- `year`: four-digit calendar year
- `month`: calendar month number from 1 to 12
- `avg_temp`: average outdoor temperature for the month in Fahrenheit
