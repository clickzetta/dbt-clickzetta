{% macro get_insert_overwrite_sql(source_relation, target_relation, existing_relation, incremental_predicates=none) %}

    {%- set dest_columns = adapter.get_columns_in_relation(target_relation) -%}
    {%- set dest_cols_csv = dest_columns | map(attribute='quoted') | join(', ') -%}
      insert overwrite table {{ target_relation }}
      {{ partition_cols(label="partition") }}
      select {{dest_cols_csv}} from {{ source_relation }}
      {%- if incremental_predicates %}
      where {{ incremental_predicates | join(' and ') }}
      {%- endif %}

{% endmacro %}


{% macro get_insert_into_sql(source_relation, target_relation, incremental_predicates=none) %}

    {%- set dest_columns = adapter.get_columns_in_relation(target_relation) -%}
    {%- set dest_cols_csv = dest_columns | map(attribute='quoted') | join(', ') -%}
    insert into table {{ target_relation }}
    select {{dest_cols_csv}} from {{ source_relation }}
    {%- if incremental_predicates %}
    where {{ incremental_predicates | join(' and ') }}
    {%- endif %}

{% endmacro %}


{% macro clickzetta__get_merge_sql(target, source, unique_key, dest_columns, incremental_predicates) %}
  {%- set predicates = [] if incremental_predicates is none else [] + incremental_predicates -%}
  {%- set dest_columns = adapter.get_columns_in_relation(target) -%}
  {%- set source_cols_csv = dest_columns | map(attribute='quoted') | join(',') -%}
  {%- set dest_cols_csv = dest_columns | map(attribute='quoted') -%}
  {%- set merge_update_columns = config.get('merge_update_columns') -%}
  {%- set merge_exclude_columns = config.get('merge_exclude_columns') -%}
  {%- set update_columns = get_merge_update_columns(merge_update_columns, merge_exclude_columns, dest_columns) -%}

  {% if not unique_key %}
    {{ exceptions.warn(
        "merge strategy without unique_key: all rows will be treated as new inserts. "
        "This may cause duplicates. Consider setting unique_key or using incremental_strategy='append'."
    ) }}
    {#-- Fall back to append behavior when no unique_key --#}
    {{ return(get_insert_into_sql(source, target, incremental_predicates)) }}
  {% endif %}

  {% if unique_key is sequence and unique_key is not mapping and unique_key is not string %}
      {% for key in unique_key %}
          {% set this_key_match %}
              DBT_INTERNAL_SOURCE.{{ key }} = DBT_INTERNAL_DEST.{{ key }}
          {% endset %}
          {% do predicates.append(this_key_match) %}
      {% endfor %}
  {% else %}
      {% set unique_key_match %}
          DBT_INTERNAL_SOURCE.{{ unique_key }} = DBT_INTERNAL_DEST.{{ unique_key }}
      {% endset %}
          {% do predicates.append(unique_key_match) %}
  {% endif %}

  {{ sql_header if sql_header is not none }}

  merge into {{ target }} as DBT_INTERNAL_DEST
      using {{ source }} as DBT_INTERNAL_SOURCE
      on {{ predicates | join(' and ') }}

  when matched then update set
      {% for column_name in update_columns -%}
          {{ column_name }} = DBT_INTERNAL_SOURCE.{{ column_name }}
          {%- if not loop.last %}, {%- endif %}
      {%- endfor %}

  when not matched then insert
     ({{source_cols_csv}})
  values (
        {% for col_name in dest_cols_csv -%}
                DBT_INTERNAL_SOURCE.{{ col_name }}
                {%- if not loop.last %}, {%- endif %}
        {%- endfor %}
    )
{% endmacro %}


{% macro dbt_clickzetta_get_incremental_sql(strategy, source, target, existing, unique_key, incremental_predicates) %}
  {%- if strategy == 'append' -%}
    {{ get_insert_into_sql(source, target, incremental_predicates) }}
  {%- elif strategy == 'insert_overwrite' -%}
    {{ get_insert_overwrite_sql(source, target, existing, incremental_predicates) }}
  {%- elif strategy == 'merge' -%}
    {{ get_merge_sql(target, source, unique_key, dest_columns=none, incremental_predicates=incremental_predicates) }}
  {%- else -%}
    {% set no_sql_for_strategy_msg -%}
      No known SQL for the incremental strategy provided: {{ strategy }}
    {%- endset %}
    {%- do exceptions.raise_compiler_error(no_sql_for_strategy_msg) -%}
  {%- endif -%}

{% endmacro %}
