{% macro clickzetta__any_value(expression) -%}
    first({{ expression }})

{%- endmacro %}
