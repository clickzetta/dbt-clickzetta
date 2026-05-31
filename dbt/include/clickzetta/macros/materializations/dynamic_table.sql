{% materialization dynamic_table, adapter='clickzetta' %}

  {#--
    Dynamic table materialization — declarative incremental refresh.
    The system automatically tracks upstream changes (INSERT/UPDATE/DELETE)
    and incrementally refreshes the table on schedule.

    Key behaviors:
    - Schema is FIXED at creation time. If the upstream source table adds a column,
      the dynamic table will NOT automatically include it — even if the model uses
      SELECT *. To pick up schema changes, run: dbt run --full-refresh
    - refresh_interval drives automatic refresh; no Studio scheduling needed.
    - Manual refresh: REFRESH DYNAMIC TABLE <name>
  --#}

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
    {#--
      Scenarios:
      1. existing_relation is none → CREATE (new table)
      2. existing_relation exists but is not a dynamic table → REPLACE (type changed)
      3. existing_relation is a dynamic table → no-op (no ALTER support yet)
      4. full_refresh → REPLACE
    --#}
    {% set full_refresh_mode = should_full_refresh() %}

    {% if existing_relation is none %}
        {% set build_sql = clickzetta__create_dynamic_table_as(target_relation, sql) %}
    {% elif full_refresh_mode or not existing_relation.is_dynamic_table %}
        {% set build_sql = clickzetta__replace_dynamic_table_as(target_relation, sql) %}
    {% else %}
        {#-- Dynamic table exists and no full_refresh: no-op (data refreshed by schedule) --#}
        {% set build_sql = '' %}
    {% endif %}

    {% do return(build_sql) %}

{% endmacro %}


{% macro dynamic_table_execute_no_op(relation) %}
    {% do store_raw_result(
        name="main",
        message="no-op — dynamic table exists and refreshes on schedule: " ~ relation,
        code="skip",
        rows_affected="-1"
    ) %}
{% endmacro %}


{% macro dynamic_table_execute_build_sql(build_sql, existing_relation, target_relation) %}

    {% call statement(name="main") %}
        {{ build_sql }}
    {% endcall %}

    {#--
      After CREATE or REPLACE, trigger an immediate refresh so the table is
      queryable right away (equivalent to Snowflake's initialize=ON_CREATE).
      Without this, the table is empty until the first scheduled refresh fires.
    --#}
    {% call statement('initialize_refresh') %}
        refresh dynamic table {{ target_relation }}
    {% endcall %}

    {%- set grant_config = config.get('grants') -%}
    {% set should_revoke = should_revoke(existing_relation, full_refresh_mode=True) %}
    {% do apply_grants(target_relation, grant_config, should_revoke=should_revoke) %}

    {% do persist_docs(target_relation, model) %}

{% endmacro %}

