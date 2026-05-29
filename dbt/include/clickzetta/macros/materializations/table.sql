{% materialization table, adapter = 'clickzetta', supported_languages=['sql', 'python'] %}
  {%- set language = model['language'] -%}
  {%- set identifier = model['alias'] -%}

  {%- set old_relation = adapter.get_relation(database=database, schema=schema, identifier=identifier) -%}
  {%- set target_relation = api.Relation.create(identifier=identifier,
                                                schema=schema,
                                                database=database,
                                                type='table') -%}
  {%- set grant_config = config.get('grants') -%}

  {{ run_hooks(pre_hooks) }}

  {% if old_relation is not none %}
    {% set is_delta = (old_relation.is_delta and config.get('file_format', validator=validation.any[basestring]) == 'delta') %}
    {% set is_iceberg = (old_relation.is_iceberg and config.get('file_format', validator=validation.any[basestring]) == 'iceberg') %}
    {% set old_relation_type = old_relation.type %}
  {% else %}
    {% set is_delta = false %}
    {% set is_iceberg = false %}
    {% set old_relation_type = target_relation.type %}
  {% endif %}

  {% if not is_delta and not is_iceberg %}
    {% set existing_relation = target_relation %}
    {{ adapter.drop_relation(existing_relation.incorporate(type=old_relation_type)) }}
  {% endif %}

  {%- set has_partition = config.get('partition_by') is not none -%}
  {%- set has_cluster = config.get('clustered_by') is not none and config.get('buckets') is not none -%}

  {%- if language == 'sql' and (has_partition or has_cluster) -%}
    {#-- Lakehouse CTAS does not support PARTITIONED BY / CLUSTERED BY. --#}
    {{ clickzetta__create_partitioned_table_as(target_relation, compiled_code) }}
  {%- else -%}
    -- build model
    {%- call statement('main', language=language) -%}
      {{ create_table_as(False, target_relation, compiled_code, language) }}
    {%- endcall -%}
  {%- endif -%}

  {% set should_revoke = should_revoke(old_relation, full_refresh_mode=True) %}
  {% do apply_grants(target_relation, grant_config, should_revoke=should_revoke) %}

  {% do persist_docs(target_relation, model) %}

  {{ run_hooks(post_hooks) }}

  {{ return({'relations': [target_relation]})}}

{% endmaterialization %}
