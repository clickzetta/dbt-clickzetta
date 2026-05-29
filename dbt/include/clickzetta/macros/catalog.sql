{% macro clickzetta__get_catalog(information_schema, schemas) -%}
  {#
    INFORMATION_SCHEMA is not reliably available in all Lakehouse environments.
    We build the catalog by iterating SHOW TABLES per schema and DESCRIBE TABLE per table.
  #}
  {% set query %}
    with catalog_data as (
      {% for schema in schemas %}
        {% set show_tables_sql %}
          SHOW TABLES IN {{ schema }}
        {% endset %}
        {% set tables = run_query(show_tables_sql) %}
        {% for row in tables %}
          {% set tbl_schema = row['schema_name'] %}
          {% set tbl_name   = row['table_name'] %}
          {% set tbl_type   = 'view' if row['is_view'] else 'table' %}
          {% set desc_sql %}
            DESCRIBE TABLE {{ tbl_schema }}.{{ tbl_name }}
          {% endset %}
          {% set cols = run_query(desc_sql) %}
          {% for col in cols %}
            select
              '{{ information_schema.database }}'  as `table_database`,
              '{{ tbl_schema }}'                   as `table_schema`,
              '{{ tbl_name }}'                     as `table_name`,
              '{{ tbl_type }}'                     as `table_type`,
              '{{ col['column_name'] }}'            as `column_name`,
              {{ loop.index }}                      as `column_index`,
              '{{ col['data_type'] }}'              as `column_type`,
              '{{ col['comment'] }}'                as `column_comment`,
              null                                  as `stats:row_count:label`,
              null                                  as `stats:row_count:value`,
              null                                  as `stats:row_count:description`,
              false                                 as `stats:row_count:include`,
              null                                  as `stats:bytes:label`,
              null                                  as `stats:bytes:value`,
              null                                  as `stats:bytes:description`,
              false                                 as `stats:bytes:include`,
              null                                  as `stats:last_modified:label`,
              null                                  as `stats:last_modified:value`,
              null                                  as `stats:last_modified:description`,
              false                                 as `stats:last_modified:include`
            {% if not loop.last %} union all {% endif %}
          {% endfor %}
          {% if not loop.last %} union all {% endif %}
        {% endfor %}
        {% if not loop.last %} union all {% endif %}
      {% endfor %}
    )
    select * from catalog_data
  {% endset %}

  {{ return(run_query(query)) }}

{%- endmacro %}
