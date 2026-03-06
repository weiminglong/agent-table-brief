{{ config(materialized='table', schema='mart') }}

-- Daily active users including employees
select
    activity_date,
    user_id
from {{ ref('stg_events') }}
group by 1, 2
