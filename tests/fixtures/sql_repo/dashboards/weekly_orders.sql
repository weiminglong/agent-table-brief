-- Weekly dashboard source
select
    order_date,
    sum(order_count) as weekly_orders
from marts.orders_by_day
group by 1
