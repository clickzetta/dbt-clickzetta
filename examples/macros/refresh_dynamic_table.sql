{% macro refresh_dynamic_table(model_name) %}
  {#
    手动触发动态表立即刷新。
    动态表通常按 refresh_interval 自动刷新，此 macro 用于需要立即获取最新数据的场景。

    用法：
      dbt run-operation refresh_dynamic_table --args '{model_name: customer_stats_dynamic}'
  #}
  {%- set relation = ref(model_name) -%}
  {% call statement('refresh_dynamic_table', fetch_result=False) %}
    refresh dynamic table {{ relation }}
  {% endcall %}
  {{ log("✓ Refreshed dynamic table: " ~ relation, info=True) }}
{% endmacro %}
