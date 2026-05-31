{% materialization clone, adapter='clickzetta' %}
  {#--
    Zero-copy clone materialization.
    Supports two scenarios:
    1. Zero-copy clone (CI/CD environment isolation): CREATE TABLE t CLONE source
    2. Time Travel clone (data recovery): CREATE TABLE t CLONE source TIMESTAMP AS OF <expression>

    Required config:
      source: fully-qualified source table name, e.g. 'example.fct_orders_partitioned'

    Optional config:
      at_timestamp: Time Travel timestamp expression, e.g. "'2024-01-05 15:00:00'"
                    Supports: string timestamp, timestamp expression, interval expression
                    Syntax: TIMESTAMP AS OF <expression>
                    Constraint: the timestamp must be >= the table's creation time.
                    For interval expressions like "current_timestamp() - interval 1 hours",
                    the source table must have existed for at least that duration.

    IMPORTANT — dependency declaration:
      The 'source' config is a plain string, so dbt cannot infer the dependency
      automatically. If the source table is also a dbt model, you must declare the
      dependency explicitly to ensure correct execution order:

        -- depends_on: {{ ref('source_table_model_name') }}

      Without this, dbt may try to clone the source before it exists.

    Usage:
      -- Zero-copy clone
      {{ config(materialized='clone', source='example.fct_orders_partitioned') }}
      -- depends_on: {{ ref('fct_orders_partitioned') }}

      -- Time Travel clone
      {{ config(
          materialized='clone',
          source='example.fct_orders_partitioned',
          at_timestamp="'2024-01-05 15:00:00'"
      ) }}
      -- depends_on: {{ ref('fct_orders_partitioned') }}
  --#}

  {%- set target_relation = this.incorporate(type='table') -%}
  {%- set existing_relation = adapter.get_relation(
        database=target_relation.database,
        schema=target_relation.schema,
        identifier=target_relation.identifier) -%}
  {%- set source_identifier = config.get('source') -%}
  {%- set at_timestamp = config.get('at_timestamp', none) -%}

  {%- if source_identifier is none -%}
    {{ exceptions.raise_compiler_error("clone materialization requires 'source' config, e.g. source='schema.table_name'") }}
  {%- endif -%}

  {{ run_hooks(pre_hooks) }}

  {#-- DROP existing relation first: CLONE does not support OR REPLACE --#}
  {%- if existing_relation is not none -%}
    {{ adapter.drop_relation(existing_relation) }}
  {%- endif -%}

  {%- call statement('main') -%}
    create table {{ target_relation }}
    clone {{ source_identifier }}
    {%- if at_timestamp is not none %}
    timestamp as of {{ at_timestamp }}
    {%- endif %}
  {%- endcall -%}

  {%- set grant_config = config.get('grants') -%}
  {#-- clone always creates a fresh table, no previous grants to revoke --#}
  {% do apply_grants(target_relation, grant_config, should_revoke=False) %}

  {{ run_hooks(post_hooks) }}

  {{ return({'relations': [target_relation]}) }}

{% endmaterialization %}
