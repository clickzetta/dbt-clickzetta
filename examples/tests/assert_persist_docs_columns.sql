-- 验证 persist_docs 列注释写入
-- dim_customers 的 customer_id / order_count / total_amount 应有非空注释
-- 返回 0 行 = 通过
{% set result = run_query("DESCRIBE TABLE " ~ ref('dim_customers')) %}
{% if execute %}
  {% set missing = [] %}
  {% set expected_cols = ['customer_id', 'order_count', 'total_amount'] %}
  {% for row in result.rows %}
    {% if row[0] in expected_cols and (row[2] is none or row[2] == '') %}
      {% do missing.append(row[0]) %}
    {% endif %}
  {% endfor %}
  {% if missing | length > 0 %}
    {{ exceptions.raise_compiler_error(
      "persist_docs column comments missing for: " ~ missing | join(', ')
    ) }}
  {% endif %}
{% endif %}

select 1 where 1 = 0
