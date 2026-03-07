{{ config(materialized='table', schema='mart') }}

-- Daily active users by product surface
select
    activity_date,
    user_id
from {{ ref('stg_events') }}
where is_employee = false
group by 1, 2
