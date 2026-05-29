{% materialization clone, adapter='clickzetta' %}
  {#--
    零拷贝克隆 materialization。
    支持两种场景：
    1. 零拷贝克隆（CI/CD 环境隔离）：CREATE TABLE t CLONE source
    2. Time Travel 克隆（数据回溯）：CREATE TABLE t CLONE source TIMESTAMP AS OF <expression>

    必填 config：
      source: 源表的完整名称，如 'example.fct_orders_partitioned'

    可选 config：
      at_timestamp: Time Travel 时间戳表达式，如 "'2024-01-05 15:00:00'"
                    支持：字符串时间戳、timestamp 表达式、interval 表达式
                    语法：TIMESTAMP AS OF <expression>

    用法：
      -- 零拷贝克隆
      {{ config(materialized='clone', source='example.fct_orders_partitioned') }}

      -- Time Travel 克隆
      {{ config(
          materialized='clone',
          source='example.fct_orders_partitioned',
          at_timestamp="'2024-01-05 15:00:00'"
      ) }}
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
