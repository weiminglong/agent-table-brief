-- Staging model for application events
select
    user_id,
    cast(event_ts as date) as activity_date,
    is_employee
from raw.app_events
