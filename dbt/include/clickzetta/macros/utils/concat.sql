{% macro clickzetta__concat(fields) -%}
    concat({{ fields|join(', ') }})
{%- endmacro %}
