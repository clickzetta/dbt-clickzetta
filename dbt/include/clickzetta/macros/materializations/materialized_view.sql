{% materialization materialized_view, adapter='clickzetta' %}
  {#--
    Lakehouse Materialized View:
    - CREATE MATERIALIZED VIEW ... AS SELECT ...
    - Does NOT support CREATE OR REPLACE; use DROP + CREATE for full_refresh.
    - REFRESH MATERIALIZED VIEW refreshes data from base tables.
    - Identified via SHOW TABLES: is_materialized_view=True
  --#}

  {%- set identifier = model['alias'] -%}
  {%- set old_relation = adapter.get_relation(database=database, schema=schema, identifier=identifier) -%}
  {%- set target_relation = api.Relation.create(
        identifier=identifier,
        schema=schema,
        database=database,
        type='table') -%}

  {{ run_hooks(pre_hooks) }}

  {%- if old_relation is not none -%}
    {#-- DROP existing MV before recreating (OR REPLACE not supported) --#}
    {%- call statement('drop_old_mv') -%}
      drop materialized view if exists {{ old_relation }}
    {%- endcall -%}
  {%- endif -%}

  {%- call statement('main') -%}
    create materialized view {{ target_relation }}
    as
    {{ compiled_code }}
  {%- endcall -%}

  {%- set grant_config = config.get('grants') -%}
  {% set should_revoke = should_revoke(old_relation, full_refresh_mode=True) %}
  {% do apply_grants(target_relation, grant_config, should_revoke=should_revoke) %}

  {% do persist_docs(target_relation, model) %}

  {{ run_hooks(post_hooks) }}

  {{ return({'relations': [target_relation]}) }}

{% endmaterialization %}
