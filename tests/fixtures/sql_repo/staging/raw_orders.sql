-- Raw orders staging table
select
    order_id,
    user_id,
    order_date,
    is_test
from raw.orders
