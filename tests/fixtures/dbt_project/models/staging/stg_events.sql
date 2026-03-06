-- Staging model for application events
select
    user_id,
    cast(event_ts as date) as activity_date,
    event_name,
    logged_in,
    is_employee
from raw.app_events
