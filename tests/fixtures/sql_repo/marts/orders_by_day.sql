-- Daily order facts
-- Excludes test orders
select
    order_date,
    user_id,
    count(*) as order_count
from staging.raw_orders
where is_test = false
group by 1, 2
