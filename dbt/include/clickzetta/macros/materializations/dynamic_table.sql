{% materialization dynamic_table, adapter='clickzetta' %}

  {% set existing_relation = load_cached_relation(this) %}
  {% set target_relation = this.incorporate(type=this.DynamicTable) %}

  {% set build_sql = dynamic_table_get_build_sql(existing_relation, target_relation) %}

  {% if build_sql == '' %}
      {{ dynamic_table_execute_no_op(target_relation) }}
  {% else %}
      {{ dynamic_table_execute_build_sql(build_sql, existing_relation, target_relation) }}
  {% endif %}

  {{ run_hooks(post_hooks) }}

  {{ return({'relations': [target_relation]}) }}

{% endmaterialization %}


{% macro dynamic_table_get_build_sql(existing_relation, target_relation) %}
    -- determine the scenario we're in: create, full_refresh, alter, refresh data
    {% if existing_relation is none %}
        {% set build_sql = clickzetta__create_dynamic_table_as(target_relation, sql) %}
    {% elif not existing_relation.is_dynamic_table %}
        {% set build_sql = clickzetta__replace_dynamic_table_as(target_relation, sql) %}
    {% endif %}

    {% do return(build_sql) %}

{% endmacro %}


{% macro dynamic_table_execute_no_op(relation) %}
    {% do store_raw_result(
        name="main",
        message="skip " ~ relation,
        code="skip",
        rows_affected="-1"
    ) %}
{% endmacro %}


{% macro dynamic_table_execute_build_sql(build_sql, existing_relation, target_relation) %}

    {% call statement(name="main") %}
        {{ build_sql }}
    {% endcall %}

    {% set should_revoke = should_revoke(existing_relation, full_refresh_mode=True) %}

    {% do persist_docs(target_relation, model) %}

{% endmacro %}

