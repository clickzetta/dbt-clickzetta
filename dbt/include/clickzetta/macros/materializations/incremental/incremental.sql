{% materialization incremental, adapter='clickzetta', supported_languages=['sql', 'python'] -%}
  {#-- Validate early so we don't run SQL if the file_format + strategy combo is invalid --#}
  {%- set raw_file_format = config.get('file_format', default='parquet') -%}
  {%- set raw_strategy = config.get('incremental_strategy') or 'merge' -%}

  {%- set file_format = dbt_clickzetta_validate_get_file_format(raw_file_format) -%}
  {%- set strategy = dbt_clickzetta_validate_get_incremental_strategy(raw_strategy, file_format) -%}

  {#-- Set vars --#}

  {%- set unique_key = config.get('unique_key', none) -%}
  {%- set partition_by = config.get('partition_by', none) -%}
  {%- set language = model['language'] -%}
  {%- set on_schema_change = incremental_validate_on_schema_change(config.get('on_schema_change'), default='ignore') -%}
  {%- set incremental_predicates = config.get('predicates', none) or config.get('incremental_predicates', none) -%}
  {%- set grant_config = config.get('grants') -%}
  {%- set vcluster = config.get('vcluster') -%}
  {%- set target_relation = this -%}
  {%- set existing_relation = load_relation(this) -%}
  {%- set tmp_relation = make_temp_relation(this) -%}

  {%- if vcluster -%}{{ clickzetta__use_vcluster(vcluster) }}{%- endif -%}

  {#-- Set Overwrite Mode --#}
  {%- if strategy == 'insert_overwrite' and partition_by -%}
    {%- call statement() -%}
      set clickzetta.sql.sources.partitionOverwriteMode = DYNAMIC
    {%- endcall -%}
  {%- endif -%}

  {#-- Run pre-hooks --#}
  {{ run_hooks(pre_hooks) }}

  {#-- Incremental run logic --#}
  {%- set has_partition = partition_by is not none -%}
  {%- set has_cluster = config.get('clustered_by') is not none and config.get('buckets') is not none -%}

  {%- if existing_relation is none -%}
    {#-- Relation must be created --#}
    {%- if language == 'sql' and (has_partition or has_cluster) -%}
      {{ clickzetta__create_partitioned_table_as(target_relation, compiled_code) }}
    {%- else -%}
      {%- call statement('main', language=language) -%}
        {{ create_table_as(False, target_relation, compiled_code, language) }}
      {%- endcall -%}
    {%- endif -%}
  {%- elif existing_relation.is_view -%}
    {#-- Relation must be dropped & recreated --#}
    {% do adapter.drop_relation(existing_relation) %}
    {%- if language == 'sql' and (has_partition or has_cluster) -%}
      {{ clickzetta__create_partitioned_table_as(target_relation, compiled_code) }}
    {%- else -%}
      {%- call statement('main', language=language) -%}
        {{ create_table_as(False, target_relation, compiled_code, language) }}
      {%- endcall -%}
    {%- endif -%}
  {%- else -%}
    {#-- Relation must be merged --#}
    {%- call statement('create_tmp_relation', language=language) -%}
      {{ create_table_as(True, tmp_relation, compiled_code, language) }}
    {%- endcall -%}
    {%- do process_schema_changes(on_schema_change, tmp_relation, existing_relation) -%}
    {%- if strategy == 'delete+insert' -%}
      {#--
        ClickZetta does not support multi-statement execution in a single call.
        delete+insert requires two separate statements: DELETE then INSERT.
        We use 'main' for DELETE (required by dbt) and 'main_insert' for INSERT.
      --#}
      {%- call statement('main') -%}
        {{ get_delete_insert_delete_sql(tmp_relation, target_relation, unique_key, incremental_predicates) }}
      {%- endcall -%}
      {%- call statement('main_insert') -%}
        {{ get_delete_insert_insert_sql(tmp_relation, target_relation, incremental_predicates) }}
      {%- endcall -%}
    {%- else -%}
      {%- call statement('main') -%}
        {{ dbt_clickzetta_get_incremental_sql(strategy, tmp_relation, target_relation, existing_relation, unique_key, incremental_predicates) }}
      {%- endcall -%}
    {%- endif -%}
    {#-- SQL tmp_relation is a view (ClickZetta has no temp tables/views); Python is a table --#}
    {%- if language == 'python' -%}
      {% call statement('drop_tmp_relation') -%}
        drop table if exists {{ tmp_relation }}
      {%- endcall %}
    {%- else -%}
      {% call statement('drop_tmp_relation') -%}
        drop view if exists {{ tmp_relation }}
      {%- endcall %}
    {%- endif -%}
  {%- endif -%}

  {% set should_revoke = should_revoke(existing_relation, full_refresh_mode) %}
  {% do apply_grants(target_relation, grant_config, should_revoke=should_revoke) %}
  {{ clickzetta__create_indexes(target_relation) }}

  {% do persist_docs(target_relation, model) %}

  {{ run_hooks(post_hooks) }}

  {{ return({'relations': [target_relation]}) }}

{%- endmaterialization %}
