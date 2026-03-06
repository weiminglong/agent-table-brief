-- Daily order facts including tests
select
    order_date,
    user_id,
    count(*) as order_count
from staging.raw_orders
group by 1, 2
