{% macro clickzetta__current_timestamp() -%}
    current_timestamp()
{%- endmacro %}

{% macro clickzetta__current_timestamp_in_utc() -%}
    {#-- Returns current time in UTC as TIMESTAMP_NTZ for consistent cross-timezone comparisons --#}
    convert_timezone('UTC', current_timestamp())
{%- endmacro %}

{% macro clickzetta__current_timestamp_backcompat() -%}
    current_timestamp()
{%- endmacro %}
