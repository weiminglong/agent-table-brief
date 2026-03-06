-- Weekly growth dashboard source
select
    activity_date,
    count(*) as dau_records
from {{ ref('daily_active_users') }}
group by 1
