{% macro clickzetta__dateadd(datepart, interval, from_date_or_timestamp) %}
    {#--
      Lakehouse natively supports DATEADD(datepart, interval, date_or_timestamp)
      for all dateparts: day, week, month, quarter, year, hour, minute, second.
      Works with both DATE and TIMESTAMP inputs.
    --#}
    dateadd({{ datepart }}, {{ interval }}, {{ from_date_or_timestamp }})
{% endmacro %}
