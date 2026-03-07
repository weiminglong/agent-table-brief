{% macro problematic_macro() %}
WITH sections AS (
    SELECT * FROM {{ ref('stg_events') }}
    {% if is_incremental() %}
    WHERE {{ incremental_predicate('block_date', 'block_number') }}
    {% endif %}
)
SELECT * FROM sections
{% endmacro %}
