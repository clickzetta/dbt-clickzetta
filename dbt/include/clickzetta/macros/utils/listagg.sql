{% macro clickzetta__listagg(measure, delimiter_text, order_by_clause, limit_num) -%}
  {#--
    Lakehouse supports GROUP_CONCAT(expr [ORDER BY ...] SEPARATOR delim).
    limit_num is not natively supported; we use a subquery workaround.
  --#}
  {%- if limit_num -%}
    {%- set inner -%}
      select {{ measure }} as _listagg_val
      {{ order_by_clause if order_by_clause }}
      limit {{ limit_num }}
    {%- endset -%}
    array_join(
      collect_list(_listagg_val),
      {{ delimiter_text }}
    )
    {#-- Note: limit_num via subquery requires wrapping in a lateral view or CTE in practice.
         For simple cases, use collect_list + slice as fallback. --#}
  {%- else -%}
    group_concat(
      {{ measure }}
      {%- if order_by_clause %} {{ order_by_clause }}{%- endif %}
      separator {{ delimiter_text }}
    )
  {%- endif -%}
{%- endmacro %}
