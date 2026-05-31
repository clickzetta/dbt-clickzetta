{# ------- UNIT TEST FIXTURE ------- #}

{# ClickZetta does not support `cast(null as string not null)` — strip the not null constraint #}
{% macro clickzetta__safe_cast(field, type) %}
    {%- set clean_type = type | replace(' not null', '') | replace(' NOT NULL', '') | trim -%}
    cast({{ field }} as {{ clean_type }})
{% endmacro %}

{# ------- GRANTS ------- #}

{% macro clickzetta__copy_grants() %}
    {{ return(False) }}
{% endmacro %}

{# ClickZetta requires "ON TABLE schema.table", not just "ON schema.table" #}
{% macro clickzetta__get_show_grant_sql(relation) %}
    {%- set rel_type = relation.type | upper if relation.type else 'TABLE' -%}
    show grants on {{ rel_type }} {{ relation.render() }}
{% endmacro %}

{# ClickZetta requires "GRANT priv ON TABLE schema.table TO ROLE/USER grantee" #}
{% macro clickzetta__get_grant_sql(relation, privilege, grantees) %}
    {%- set rel_type = relation.type | upper if relation.type else 'TABLE' -%}
    {% set grant_sqls = [] %}
    {% for grantee in grantees %}
        {% set grantee_type = "USER" if grantee.startswith("user:") else "ROLE" %}
        {% set grantee_name = grantee[5:] if grantee.startswith("user:") else grantee %}
        {% do grant_sqls.append(
            "grant " ~ privilege ~ " on " ~ rel_type ~ " " ~ relation.render() ~ " to " ~ grantee_type ~ " " ~ grantee_name
        ) %}
    {% endfor %}
    {{ return(grant_sqls | join("; ")) }}
{% endmacro %}

{% macro clickzetta__get_revoke_sql(relation, privilege, grantees) %}
    {%- set rel_type = relation.type | upper if relation.type else 'TABLE' -%}
    {% set revoke_sqls = [] %}
    {% for grantee in grantees %}
        {% set grantee_type = "USER" if grantee.startswith("user:") else "ROLE" %}
        {% set grantee_name = grantee[5:] if grantee.startswith("user:") else grantee %}
        {% do revoke_sqls.append(
            "revoke " ~ privilege ~ " on " ~ rel_type ~ " " ~ relation.render() ~ " from " ~ grantee_type ~ " " ~ grantee_name
        ) %}
    {% endfor %}
    {{ return(revoke_sqls | join("; ")) }}
{% endmacro %}

{# ClickZetta does not support multiple DCL statements in one call #}
{% macro clickzetta__call_dcl_statements(dcl_statement_list) %}
    {% for dcl_statement in dcl_statement_list %}
        {% call statement('grants') %}
            {{ dcl_statement }}
        {% endcall %}
    {% endfor %}
{% endmacro %}

{# ------- END GRANTS ------- #}

{# ------- INDEXES ------- #}

{#
  Create indexes after table creation.
  Supports bloomfilter, inverted, and vector index types.

  Usage in model config:
    {{ config(
        materialized='table',
        indexes=[
            {'type': 'bloomfilter', 'columns': ['order_id']},
            {'type': 'bloomfilter', 'columns': ['customer_id'], 'name': 'idx_cust'},
            {'type': 'inverted', 'columns': ['status']},
            {'type': 'inverted', 'columns': ['description'], 'analyzer': 'unicode'},
            {'type': 'vector', 'columns': ['embedding'], 'distance_function': 'cosine_distance'},
            {'type': 'vector', 'columns': ['vec'], 'distance_function': 'l2_distance', 'scalar_type': 'f32'}
        ]
    ) }}

  Notes:
  - Index name must be in the same schema as the table (use schema.index_name syntax)
  - For dbt models, BUILD INDEX is not needed: dbt always writes fresh data after CREATE TABLE,
    so new data is automatically indexed
  - bloomfilter: single column only, optional ngram analyzer
  - inverted: single column, optional analyzer (unicode, stemmer, chinese, etc.)
  - vector: single column, distance_function required (cosine_distance, l2_distance, dot_product,
    jaccard_distance, hamming_distance), optional scalar_type (f32, f16, b1)
#}
{% macro clickzetta__create_indexes(relation) %}
  {%- set indexes = config.get('indexes', []) -%}
  {%- if indexes -%}
    {%- for index in indexes -%}
      {%- set index_type = index.get('type', 'bloomfilter') | lower -%}
      {%- set columns = index.get('columns', []) -%}
      {%- if columns is string -%}{%- set columns = [columns] -%}{%- endif -%}

      {%- for col in columns -%}
        {%- set default_name = relation.schema ~ '_' ~ relation.identifier ~ '_' ~ col ~ '_' ~ index_type ~ '_idx' -%}
        {%- set index_name = index.get('name', default_name) -%}
        {#-- Use three-part name when database is available --#}
        {%- if relation.database is not none and relation.database | string != 'None' -%}
          {%- set qualified_name = relation.database ~ '.' ~ relation.schema ~ '.' ~ index_name -%}
        {%- else -%}
          {%- set qualified_name = relation.schema ~ '.' ~ index_name -%}
        {%- endif -%}

        {%- if index_type == 'bloomfilter' -%}
          {%- set analyzer = index.get('analyzer', none) -%}
          {% call statement('create_index_' ~ loop.index) %}
            create bloomfilter index if not exists {{ qualified_name }}
            on table {{ relation }}({{ col }})
            {%- if analyzer is not none %} properties('analyzer'='{{ analyzer }}'){%- endif %}
          {% endcall %}

        {%- elif index_type == 'inverted' -%}
          {%- set analyzer = index.get('analyzer', none) -%}
          {% call statement('create_index_' ~ loop.index) %}
            create inverted index if not exists {{ qualified_name }}
            on table {{ relation }}({{ col }})
            {%- if analyzer is not none %} properties('analyzer'='{{ analyzer }}'){%- endif %}
          {% endcall %}

        {%- elif index_type == 'vector' -%}
          {%- set distance_fn = index.get('distance_function', 'cosine_distance') -%}
          {%- set scalar_type = index.get('scalar_type', none) -%}
          {% call statement('create_index_' ~ loop.index) %}
            create vector index if not exists {{ qualified_name }}
            on table {{ relation }}({{ col }})
            properties(
              "distance.function" = "{{ distance_fn }}"
              {%- if scalar_type is not none %}, "scalar.type" = "{{ scalar_type }}"{%- endif %}
            )
          {% endcall %}

        {%- else -%}
          {{ exceptions.raise_compiler_error("Unsupported index type: '" ~ index_type ~ "'. Supported types: bloomfilter, inverted, vector") }}
        {%- endif -%}
      {%- endfor -%}
    {%- endfor -%}
  {%- endif -%}
{% endmacro %}


{# ------- OPTIMIZE ------- #}

{#
  Merge small files for a table or specific partitions.
  Useful after high-frequency incremental writes.

  Usage as post-hook:
    {{ config(post_hook="{{ clickzetta__optimize_table(this) }}") }}

  Or with partition filter:
    {{ config(post_hook="{{ clickzetta__optimize_table(this, 'dt >= current_date() - interval 7 days') }}") }}

  Or via run-operation:
    dbt run-operation optimize_table --args '{relation: example.my_table}'
#}
{% macro clickzetta__optimize_table(relation, where=none) %}
  {% set optimize_sql %}
    optimize {{ relation }}
    {%- if where is not none %} where {{ where }}{%- endif %}
  {% endset %}
  {% do run_query(optimize_sql) %}
  {% if execute %}
    {{ log("Optimized " ~ relation ~ (" where " ~ where if where else ""), info=true) }}
  {% endif %}
{% endmacro %}

{% macro optimize_table(relation, where=none) %}
  {{ clickzetta__optimize_table(relation, where) }}
{% endmacro %}

{# ------- VCLUSTER ------- #}

{#
  Switch the active VCluster for the current session before running a model.
  Useful for resource isolation: large models use a bigger cluster, small models use a smaller one.

  Usage in model config (applied automatically via pre-hook in table/incremental materializations):
    {{ config(vcluster='large_ap') }}

  Or as an explicit pre-hook:
    {{ config(pre_hook="{{ clickzetta__use_vcluster('large_ap') }}") }}

  Or via run-operation to switch manually:
    dbt run-operation use_vcluster --args '{vcluster: large_ap}'
#}
{% macro clickzetta__use_vcluster(vcluster) %}
  {% if vcluster and execute %}
    {# Validate vcluster exists before switching #}
    {% set existing = run_query("show vclusters") %}
    {% set names = existing.columns[0].values() | map('upper') | list %}
    {% if vcluster | upper not in names %}
      {{ exceptions.raise_compiler_error(
        "VCluster '" ~ vcluster ~ "' does not exist. Available: " ~ names | join(', ')
      ) }}
    {% endif %}
    {% call statement('use_vcluster') %}
      use vcluster {{ vcluster }}
    {% endcall %}
    {{ log("Switched to VCluster: " ~ vcluster, info=true) }}
  {% endif %}
{% endmacro %}

{% macro use_vcluster(vcluster) %}
  {{ clickzetta__use_vcluster(vcluster) }}
{% endmacro %}

{# ------- UNDROP / DROP ------- #}

{#
  Recover a recently dropped object within the retention period.
  Supports: table, dynamic table, materialized view, table stream.
  All use the same UNDROP TABLE syntax regardless of original object type.
  Does NOT support: view, external table, schema, index, function, etc.

  Usage:
    dbt run-operation undrop --args '{relation: example.my_table}'

  To list recently dropped tables first:
    dbt run-operation show_tables_history --args '{schema: example}'
#}
{% macro undrop(relation) %}
  {% set sql %}undrop table {{ relation }}{% endset %}
  {% do run_query(sql) %}
  {% if execute %}
    {{ log("Recovered: " ~ relation, info=true) }}
  {% endif %}
{% endmacro %}

{# Keep undrop_table as alias for backwards compatibility #}
{% macro undrop_table(relation) %}
  {{ undrop(relation) }}
{% endmacro %}

{% macro show_tables_history(schema) %}
  {% set sql %}show tables history in {{ schema }}{% endset %}
  {% set results = run_query(sql) %}
  {% if execute %}
    {% for row in results.rows %}
      {{ log(row | join(' | '), info=true) }}
    {% endfor %}
  {% endif %}
{% endmacro %}

{#
  Drop an object by type. Useful for manual cleanup via run-operation.
  type: table | view | dynamic_table | materialized_view | stream

  Usage:
    dbt run-operation drop_object --args '{relation: example.my_table, type: table}'
    dbt run-operation drop_object --args '{relation: example.my_view, type: view}'

  Note: table, dynamic_table, materialized_view, and stream support UNDROP recovery.
        view, external table, schema do NOT support recovery.
  Note: Named drop_object (not drop_relation) to avoid conflict with dbt-core's built-in drop_relation macro.
#}
{% macro drop_object(relation, type='table') %}
  {% if execute %}
    {%- set drop_type = type | replace('_', ' ') -%}
    {% set sql %}drop {{ drop_type }} if exists {{ relation }}{% endset %}
    {% do run_query(sql) %}
    {{ log("Dropped " ~ type ~ ": " ~ relation, info=true) }}
  {% endif %}
{% endmacro %}

{# ------- END UNDROP / DROP ------- #}

{% macro dbt_clickzetta_tblproperties_clause() -%}
  {%- set tblproperties = config.get('tblproperties') -%}
  {%- if tblproperties is not none %}
    tblproperties (
      {%- for prop in tblproperties -%}
      '{{ prop }}' = '{{ tblproperties[prop] }}' {% if not loop.last %}, {% endif %}
      {%- endfor %}
    )
  {%- endif %}
{%- endmacro -%}

{% macro file_format_clause() %}
  {{ return(adapter.dispatch('file_format_clause', 'dbt')()) }}
{%- endmacro -%}

{% macro clickzetta__file_format_clause() %}
  {%- set file_format = config.get('file_format', validator=validation.any[basestring]) -%}
  {%- if file_format is not none %}
    using {{ file_format }}
  {%- endif %}
{%- endmacro -%}


{% macro location_clause() %}
  {{ return(adapter.dispatch('location_clause', 'dbt')()) }}
{%- endmacro -%}

{% macro clickzetta__location_clause() %}
  {%- set location_root = config.get('location_root', validator=validation.any[basestring]) -%}
  {%- set identifier = model['alias'] -%}
  {%- if location_root is not none %}
    location '{{ location_root }}/{{ identifier }}'
  {%- endif %}
{%- endmacro -%}


{% macro options_clause() -%}
  {{ return(adapter.dispatch('options_clause', 'dbt')()) }}
{%- endmacro -%}

{% macro clickzetta__options_clause() -%}
  {%- set options = config.get('options') -%}
  {%- if config.get('file_format') == 'hudi' -%}
    {%- set unique_key = config.get('unique_key') -%}
    {%- if unique_key is not none and options is none -%}
      {%- set options = {'primaryKey': config.get('unique_key')} -%}
    {%- elif unique_key is not none and options is not none and 'primaryKey' not in options -%}
      {%- set _ = options.update({'primaryKey': config.get('unique_key')}) -%}
    {%- elif options is not none and 'primaryKey' in options and options['primaryKey'] != unique_key -%}
      {{ exceptions.raise_compiler_error("unique_key and options('primaryKey') should be the same column(s).") }}
    {%- endif %}
  {%- endif %}

  {%- if options is not none %}
    options (
      {%- for option in options -%}
      {{ option }} "{{ options[option] }}" {% if not loop.last %}, {% endif %}
      {%- endfor %}
    )
  {%- endif %}
{%- endmacro -%}


{% macro comment_clause() %}
  {{ return(adapter.dispatch('comment_clause', 'dbt')()) }}
{%- endmacro -%}

{% macro clickzetta__comment_clause() %}
  {%- set raw_persist_docs = config.get('persist_docs', {}) -%}

  {%- if raw_persist_docs is mapping -%}
    {%- set raw_relation = raw_persist_docs.get('relation', false) -%}
      {%- if raw_relation -%}
      comment '{{ model.description | replace("'", "\\'") }}'
      {% endif %}
  {%- elif raw_persist_docs -%}
    {{ exceptions.raise_compiler_error("Invalid value provided for 'persist_docs'. Expected dict but got value: " ~ raw_persist_docs) }}
  {% endif %}
{%- endmacro -%}


{% macro partition_cols(label, required=false) %}
  {{ return(adapter.dispatch('partition_cols', 'dbt')(label, required)) }}
{%- endmacro -%}

{% macro clickzetta__partition_cols(label, required=false) %}
  {%- set cols = config.get('partition_by', validator=validation.any[list, basestring]) -%}
  {%- if cols is not none %}
    {%- if cols is string -%}
      {%- set cols = [cols] -%}
    {%- endif -%}
    {{ label }} (
    {%- for item in cols -%}
      {{ item }}
      {%- if not loop.last -%},{%- endif -%}
    {%- endfor -%}
    )
  {%- endif %}
{%- endmacro -%}


{% macro clustered_cols(label, required=false) %}
  {{ return(adapter.dispatch('clustered_cols', 'dbt')(label, required)) }}
{%- endmacro -%}

{% macro clickzetta__clustered_cols(label, required=false) %}
  {%- set cols = config.get('clustered_by', validator=validation.any[list, basestring]) -%}
  {%- set buckets = config.get('buckets', validator=validation.any[int]) -%}
  {%- if (cols is not none) and (buckets is not none) %}
    {%- if cols is string -%}
      {%- set cols = [cols] -%}
    {%- endif -%}
    {{ label }} (
    {%- for item in cols -%}
      {{ item }}
      {%- if not loop.last -%},{%- endif -%}
    {%- endfor -%}
    ) into {{ buckets }} buckets
  {%- endif %}
{%- endmacro -%}


{% macro fetch_tbl_properties(relation) -%}
  {% call statement('list_properties', fetch_result=True) -%}
    SHOW TBLPROPERTIES {{ relation }}
  {% endcall %}
  {% do return(load_result('list_properties').table) %}
{%- endmacro %}


{% macro create_temporary_view(relation, compiled_code) -%}
  {{ return(adapter.dispatch('create_temporary_view', 'dbt')(relation, compiled_code)) }}
{%- endmacro -%}

{#-- We can't use temporary tables with `create ... as ()` syntax --#}
{% macro clickzetta__create_temporary_view(relation, compiled_code) -%}
    create or replace view {{ relation }} as
      {{ compiled_code }}
{%- endmacro -%}


{%- macro clickzetta__create_table_as(temporary, relation, compiled_code, language='sql') -%}
  {%- if language == 'sql' -%}
    {%- if temporary -%}
      {{ create_temporary_view(relation, compiled_code) }}
    {%- else -%}
      {%- set contract_config = config.get('contract') -%}
      {%- if contract_config.enforced -%}
        {{ get_assert_columns_equivalent(compiled_code) }}
        {%- set compiled_code = get_select_subquery(compiled_code) %}
      {% endif %}
      create table {{ relation }}
      {{ file_format_clause() }}
      {{ options_clause() }}
      {{ partition_cols(label="partitioned by") }}
      {{ clustered_cols(label="clustered by") }}
      {{ location_clause() }}
      {{ comment_clause() }}
      as
      {{ compiled_code }}
    {%- endif -%}
  {%- elif language == 'python' -%}
    {#--
    N.B. Python models _can_ write to temp views HOWEVER they use a different session
    and have already expired by the time they need to be used (I.E. in merges for incremental models)

    TODO: Deep dive into clickzetta sessions to see if we can reuse a single session for an entire
    dbt invocation.
     --#}
    {{ py_write_table(compiled_code=compiled_code, target_relation=relation) }}
  {%- endif -%}
{%- endmacro -%}

{#--
  clickzetta__create_partitioned_table_as:
  Lakehouse CTAS does not support PARTITIONED BY / CLUSTERED BY.
  This macro creates a partitioned table by:
    1. Creating a tmp view to infer column types
    2. DESCRIBE TABLE to get col defs
    3. CREATE TABLE (explicit cols) PARTITIONED BY
    4. INSERT INTO from tmp view
  Returns the list of statement names executed.
--#}
{% macro clickzetta__create_partitioned_table_as(relation, compiled_code) %}
  {%- set partition_by = config.get('partition_by', []) -%}
  {%- if partition_by is string -%}{%- set partition_by = [partition_by] -%}{%- endif -%}
  {%- set partition_by_lower = partition_by | map('lower') | list -%}

  {%- set tmp_view = make_temp_relation(relation) -%}

  {%- call statement('create_tmp_view_for_partition') -%}
    create or replace view {{ tmp_view }} as {{ compiled_code }}
  {%- endcall -%}

  {%- set describe_result = run_query('DESCRIBE TABLE ' ~ tmp_view) -%}
  {%- set data_cols = [] -%}
  {%- set part_col_defs = [] -%}
  {%- set all_col_names = [] -%}
  {%- for row in describe_result.rows -%}
    {%- set col_name = row['column_name'] -%}
    {%- set col_type = row['data_type'].split(' ')[0] -%}
    {%- do all_col_names.append(col_name) -%}
    {%- if col_name | lower in partition_by_lower -%}
      {%- do part_col_defs.append(col_name ~ ' ' ~ col_type) -%}
    {%- else -%}
      {%- do data_cols.append(col_name ~ ' ' ~ col_type) -%}
    {%- endif -%}
  {%- endfor -%}

  {%- call statement('create_partitioned_table') -%}
    create table {{ relation }}
    ({{ data_cols | join(', ') }})
    {%- if part_col_defs %}
    partitioned by ({{ part_col_defs | join(', ') }})
    {%- endif %}
    {{ clustered_cols(label="clustered by") }}
  {%- endcall -%}

  {%- call statement('main') -%}
    insert into {{ relation }} ({{ all_col_names | join(', ') }})
    select {{ all_col_names | join(', ') }} from {{ tmp_view }}
  {%- endcall -%}

  {%- call statement('drop_tmp_view_for_partition') -%}
    drop view if exists {{ tmp_view }}
  {%- endcall -%}
{% endmacro %}

{% macro clickzetta__create_dynamic_table_as(relation, sql) -%}
  {% set target_lag = config.get('target_lag') %}
  create dynamic table {{ relation }}
    {% if target_lag is not none %}
      TARGET_LAG '{{ target_lag }}'
    {% endif %}
    {{ partition_cols(label="partitioned by") }}
    {{ clustered_cols(label="clustered by") }}
    {{ refresh_interval() }}
    as
    {{ sql }}
{%- endmacro %}

{% macro clickzetta__replace_dynamic_table_as(relation, sql) %}
  {% set target_lag = config.get('target_lag') %}
  create or replace dynamic table {{ relation }}
    {% if target_lag is not none %}
      TARGET_LAG '{{ target_lag }}'
    {% endif %}
    {{ partition_cols(label="partitioned by") }}
    {{ clustered_cols(label="clustered by") }}
    {{ refresh_interval() }}
    as
    {{ sql }}
{% endmacro %}

{% macro alter_table_add_constraints(relation, constraints) %}
  {{ return(adapter.dispatch('alter_table_add_constraints', 'dbt')(relation, constraints)) }}
{% endmacro %}

{% macro clickzetta__alter_table_add_constraints(relation, constraints) %}
  {% for constraint in constraints %}
    {% if constraint.type == 'check' and not is_incremental() %}
      {%- set constraint_hash = local_md5(column_name ~ ";" ~ constraint.expression ~ ";" ~ loop.index) -%}
      {% call statement() %}
        alter table {{ relation }} add constraint {{ constraint.name if constraint.name else constraint_hash }} check {{ constraint.expression }};
      {% endcall %}
    {% endif %}
  {% endfor %}
{% endmacro %}

{% macro alter_column_set_constraints(relation, column_dict) %}
  {{ return(adapter.dispatch('alter_column_set_constraints', 'dbt')(relation, column_dict)) }}
{% endmacro %}

{% macro clickzetta__alter_column_set_constraints(relation, column_dict) %}
  {% for column_name in column_dict %}
    {% set constraints = column_dict[column_name]['constraints'] %}
    {% for constraint in constraints %}
      {% if constraint.type != 'not_null' %}
        {{ exceptions.warn('Invalid constraint for column ' ~ column_name ~ '. Only `not_null` is supported.') }}
      {% else %}
        {% set quoted_name = adapter.quote(column_name) if column_dict[column_name]['quote'] else column_name %}
        {% call statement() %}
          alter table {{ relation }} change column {{ quoted_name }} set not null {{ constraint.expression or "" }};
        {% endcall %}
      {% endif %}
    {% endfor %}
  {% endfor %}
{% endmacro %}


{% macro clickzetta__create_view_as(relation, sql) -%}
  create or replace view {{ relation }}
  {{ comment_clause() }}
  {%- set contract_config = config.get('contract') -%}
  {%- if contract_config.enforced -%}
    {{ get_assert_columns_equivalent(sql) }}
  {%- endif %}
  as
    {{ sql }}
{% endmacro %}

{% macro clickzetta__create_schema(relation) -%}
  {%- call statement('create_schema') -%}
    create schema if not exists {{relation}}
  {% endcall %}
{% endmacro %}

{% macro clickzetta__drop_schema(relation) -%}
  {%- call statement('drop_schema') -%}
    drop schema if exists {{ relation }} cascade
  {%- endcall -%}
{% endmacro %}

{% macro get_columns_in_relation_raw(relation) -%}
  {{ return(adapter.dispatch('get_columns_in_relation_raw', 'dbt')(relation)) }}
{%- endmacro -%}

{% macro clickzetta__get_columns_in_relation_raw(relation) -%}
  {% call statement('get_columns_in_relation_raw', fetch_result=True) %}
      show columns in {{ relation }}
  {% endcall %}
  {% do return(load_result('get_columns_in_relation_raw').table) %}
{% endmacro %}

{% macro clickzetta__get_columns_in_relation(relation) -%}
  {% call statement('get_columns_in_relation', fetch_result=True) %}
      show columns in {{ relation.include(schema=(schema is not none)) }}
  {% endcall %}
  {% do return(load_result('get_columns_in_relation').table) %}
{% endmacro %}

{% macro clickzetta__list_relations_without_caching(relation) %}
  {% call statement('list_relations_without_caching', fetch_result=True) -%}
    show tables in {{ relation }}
  {% endcall %}

  {% do return(load_result('list_relations_without_caching').table) %}
{% endmacro %}

{% macro list_relations_show_tables_without_caching(schema_relation) %}
  {% call statement('list_relations_without_caching_show_tables', fetch_result=True) -%}
    show tables in {{ schema_relation }}
  {% endcall %}

  {% do return(load_result('list_relations_without_caching_show_tables').table) %}
{% endmacro %}

{% macro describe_table_extended_without_caching(table_name) %}
  {% call statement('describe_table_extended_without_caching', fetch_result=True) -%}
    describe extended {{ table_name }}
  {% endcall %}
  {% do return(load_result('describe_table_extended_without_caching').table) %}
{% endmacro %}

{% macro clickzetta__list_schemas(database) -%}
  {% call statement('list_schemas', fetch_result=True, auto_begin=False) %}
    show schemas
    {%- if database is not none and database | string != 'None' %} in {{ database }}{% endif %}
  {% endcall %}
  {{ return(load_result('list_schemas').table) }}
{% endmacro %}

{% macro clickzetta__rename_relation(from_relation, to_relation) -%}
  {% call statement('rename_relation') -%}
    {% if not from_relation.type %}
      {% do exceptions.raise_database_error("Cannot rename a relation with a blank type: " ~ from_relation.identifier) %}
    {% elif from_relation.type == 'table' %}
        alter table {{ from_relation }} rename to {{ to_relation }}
    {% elif from_relation.type == 'view' %}
        alter view {{ from_relation }} rename to {{ to_relation }}
    {% elif from_relation.type == 'dynamic_table' %}
        alter dynamic table {{ from_relation }} rename to {{ to_relation }}
    {% elif from_relation.type == 'materialized_view' %}
        alter materialized view {{ from_relation }} rename to {{ to_relation }}
    {% elif from_relation.type == 'stream' %}
      {% do exceptions.raise_compiler_error("Table Streams cannot be renamed. Drop and recreate the stream: " ~ from_relation.identifier) %}
    {% else %}
      {% do exceptions.raise_database_error("Cannot rename relation of type '" ~ from_relation.type ~ "': " ~ from_relation.identifier) %}
    {% endif %}
  {%- endcall %}
{% endmacro %}

{% macro clickzetta__drop_relation(relation) -%}
  {#--
    ClickZetta's IF EXISTS only suppresses "object not found" errors, NOT type mismatches.
    So we cannot blindly issue DROP TABLE + DROP VIEW — if the object exists as the wrong
    type, ClickZetta raises an error.

    When type is known AND is not 'table': issue the correct DROP directly.
    When type is None or 'table': query SHOW TABLES to discover the actual type first.

    Why type='table' also needs a lookup:
    ClickZetta has no temp table support. When dbt calls create_table_as(temporary=True),
    the adapter creates a regular VIEW instead. dbt still passes type='table' to
    drop_relation, but the actual object is a VIEW — so DROP TABLE would fail.
    Querying SHOW TABLES reveals the actual type and issues the correct DROP.
  --#}
  {%- if relation.type is not none and relation.type | string != 'None' and relation.type | string != 'table' -%}
    {%- set drop_type = relation.type | string | replace('_', ' ') -%}
    {% call statement('drop_relation', auto_begin=False) -%}
      drop {{ drop_type }} if exists {{ relation }}
    {%- endcall %}
  {%- else -%}
    {#-- Type unknown: query SHOW TABLES to find the actual object type --#}
    {%- if execute -%}
      {#-- Use database prefix for SHOW TABLES. Fall back to target.database if relation.database is None
           (happens when manifest database=None due to parse-phase generate_database_name limitation) --#}
      {%- set db = relation.database if (relation.database is not none and relation.database | string != 'None') else target.database -%}
      {%- set schema_ref = (db ~ '.' ~ relation.schema) if db else relation.schema -%}
      {%- set show_result = run_query('SHOW TABLES IN ' ~ schema_ref ~ ' LIKE \'' ~ relation.identifier ~ '\'') -%}
      {#-- Use namespace to allow set inside for loop (Jinja2 scoping rule) --#}
      {%- set ns = namespace(actual_type=none) -%}
      {%- for row in show_result.rows -%}
        {%- if row['table_name'] | lower == relation.identifier | lower -%}
          {%- if row['is_dynamic'] -%}
            {%- set ns.actual_type = 'dynamic table' -%}
          {%- elif row['is_materialized_view'] -%}
            {%- set ns.actual_type = 'materialized view' -%}
          {%- elif row['is_view'] -%}
            {%- set ns.actual_type = 'view' -%}
          {%- else -%}
            {%- set ns.actual_type = 'table' -%}
          {%- endif -%}
        {%- endif -%}
      {%- endfor -%}
      {%- if ns.actual_type is not none -%}
        {% call statement('drop_relation', auto_begin=False) -%}
          drop {{ ns.actual_type }} if exists {{ relation }}
        {%- endcall %}
      {%- endif -%}
      {#-- Also check streams (not returned by SHOW TABLES) --#}
      {%- if ns.actual_type is none -%}
        {%- set stream_result = run_query('SHOW STREAMS IN ' ~ schema_ref) -%}
        {%- set ns2 = namespace(found=false) -%}
        {%- for row in stream_result.rows -%}
          {%- if row['name'] | lower == relation.identifier | lower -%}
            {%- set ns2.found = true -%}
            {% call statement('drop_relation_stream', auto_begin=False) -%}
              drop stream if exists {{ relation }}
            {%- endcall %}
          {%- endif -%}
        {%- endfor -%}
      {%- endif -%}
    {%- endif -%}
  {%- endif %}
{% endmacro %}


{% macro clickzetta__generate_database_name(custom_database_name=none, node=none) -%}
  {# ClickZetta workspace maps to dbt database. Use custom name if provided, else target workspace. #}
  {%- if custom_database_name is not none -%}
    {{ custom_database_name | trim }}
  {%- else -%}
    {{ target.database | trim }}
  {%- endif -%}
{%- endmacro %}

{% macro clickzetta__persist_docs(relation, model, for_relation, for_columns) -%}
  {% if for_columns and config.persist_column_docs() and model.columns %}
    {% do alter_column_comment(relation, model.columns) %}
  {% endif %}
{% endmacro %}

{% macro clickzetta__alter_column_comment(relation, column_dict) %}
  {% for column_name in column_dict %}
    {% set comment = column_dict[column_name]['description'] %}
    {% set escaped_comment = comment | replace('\'', '\\\'') %}
    {% set comment_query %}
      alter table {{ relation }} change column
          {{ adapter.quote(column_name) if column_dict[column_name]['quote'] else column_name }}
          comment '{{ escaped_comment }}';
    {% endset %}
    {% do run_query(comment_query) %}
  {% endfor %}
{% endmacro %}


{#--
  ── Table Stream notes ────────────────────────────────────────────────────────

  ClickZetta Table Streams are NOT created by dbt materializations — they must
  be created manually (or via pre_hook) before being used as dbt sources.

  Required syntax (TABLE_STREAM_MODE is mandatory):
    CREATE TABLE STREAM <schema>.<name>
      ON TABLE <schema>.<source_table>
      WITH PROPERTIES ('TABLE_STREAM_MODE' = 'STANDARD')   -- or 'APPEND_ONLY'

  SHOW_INITIAL_ROWS behavior:
    WITH PROPERTIES ('TABLE_STREAM_MODE' = 'STANDARD', 'SHOW_INITIAL_ROWS' = 'TRUE')
    SHOW_INITIAL_ROWS only captures rows that exist in the source table AT THE TIME
    the stream is created. Rows inserted AFTER stream creation appear as normal
    change events (INSERT __change_type), not as initial rows.
    Correct order: INSERT data → CREATE STREAM (with SHOW_INITIAL_ROWS=TRUE)

  Stream COMMENT support:
    CREATE TABLE STREAM <name> ON TABLE <source>
      WITH PROPERTIES ('TABLE_STREAM_MODE' = 'STANDARD')
      COMMENT 'description of this stream'
    Visible via: DESC STREAM <name>

  Stream as dbt source:
    Define in sources.yml with schema pointing to the stream's schema.
    System columns (__change_type, __commit_version, __commit_timestamp) are
    accessible in SELECT. get_columns_in_relation() returns [] for streams
    (system columns are filtered) — this is intentional.

  Dependency declaration for pre_hook streams:
    If a dbt model creates a stream via pre_hook and another model reads it,
    declare the dependency explicitly:
      -- depends_on: {{ ref('model_that_creates_stream') }}
--#}


{% macro clickzetta__make_temp_relation(base_relation, suffix) %}
    {% set tmp_identifier = base_relation.identifier ~ suffix %}
    {% set tmp_relation = base_relation.incorporate(path = {
        "identifier": tmp_identifier
    }) -%}

    {% do return(tmp_relation) %}
{% endmacro %}


{% macro clickzetta__alter_column_type(relation, column_name, new_column_type) -%}
  {% set replace_new_column_type = new_column_type | replace('not null', '') %}
  {% call statement('alter_column_type') %}
    alter table {{ relation }} alter column {{ column_name }} type {{ replace_new_column_type }};
  {% endcall %}
{% endmacro %}


{% macro clickzetta__alter_relation_add_remove_columns(relation, add_columns, remove_columns) %}

  {#-- Lakehouse supports both ADD COLUMNS and DROP COLUMN --#}

  {% if remove_columns %}
    {% for column in remove_columns %}
      {% call statement('remove_column_' ~ loop.index) %}
        alter table {{ relation }} drop column {{ column.name }}
      {% endcall %}
    {% endfor %}
  {% endif %}

  {% if add_columns and add_columns | length > 0 %}
    {% call statement('add_columns') %}
      alter {{ relation.type }} {{ relation }}
      add columns (
        {% for column in add_columns %}
          {{ column.name }} {{ column.data_type }}{{ ',' if not loop.last }}
        {% endfor %}
      )
    {% endcall %}
  {% endif %}

{% endmacro %}

{%- macro clickzetta__information_schema(relation) -%}
  SYS.INFORMATION_SCHEMA
{%- endmacro -%}


{%- macro refresh_interval() -%}
  {% set refresh_interval = config.get('refresh_interval') %}
  {% set refresh_vc = config.get('refresh_vc') %}
  {% if refresh_interval is not none %}
    refresh interval {{refresh_interval}}
    {%- if refresh_vc is not none %} vcluster {{refresh_vc}}{% endif %}
  {% endif %}
{%- endmacro -%}

{%- macro refresh_vc() -%}
  {#-- vcluster is now inlined into refresh_interval() — this macro is a no-op --#}
{%- endmacro -%}

{%- macro dynamic_table_initialize() -%}
  {% set initialize = config.get('initialize') %}
  {% if initialize is none %}
    INITIALIZE = ON_SCHEDULE
  {% else %}
    INITIALIZE = {{ initialize }}
  {% endif %}
{%- endmacro -%}