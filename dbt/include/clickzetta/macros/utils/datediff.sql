{% macro clickzetta__datediff(first_date, second_date, datepart) %}
    {#--
      Lakehouse natively supports DATEDIFF(datepart, start, end) for:
        day, week, month, quarter, year, hour, minute, second
      Returns integer (truncated, not rounded).
      Note: week = floor(days/7), not calendar-week-boundary aware.
    --#}
    {%- if datepart == 'week' -%}
        {#-- Lakehouse DATEDIFF(week,...) is not available; compute from days --#}
        floor(datediff(day, {{ first_date }}, {{ second_date }}) / 7)
    {%- else -%}
        datediff({{ datepart }}, {{ first_date }}, {{ second_date }})
    {%- endif -%}
{% endmacro %}
