{{ config(materialized='incremental', schema='mart') }}

-- Daily active users by product surface
-- Excludes employees and keeps logged-in usage only
select
    e.activity_date,
    e.user_id
from {{ ref('stg_events') }} as e
join {{ ref('dim_users') }} as u on e.user_id = u.user_id
where e.is_employee = false
  and e.logged_in = true
group by 1, 2
