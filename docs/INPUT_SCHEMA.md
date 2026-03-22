# Input Schema Notes

The deployed MVP expects an uploaded utility-bill CSV and optional building metadata entered in the Streamlit sidebar.

## Utility Bill CSV

- `billing_start`: billing period start date
- `billing_end`: billing period end date
- `utility_type`: `electricity` or `gas`
- `usage`: billed consumption for the period
- `usage_unit`: normalized unit such as `kwh` or `therms`
- `cost`: billed cost in USD

## Weather Lookup Inputs

- `ZIP code`: preferred geocoding input for U.S. buildings
- `Address`: optional fallback when ZIP code is not provided or when address-based lookup is preferred

## Building Metadata Inputs

- `building_name`
- `building_type`
- `floor_area_sqft`
- `year_built`
