{% macro clickzetta__bool_or(expression) -%}

    max({{ expression }})

{%- endmacro %}
