{% macro clickzetta__get_catalog(information_schema, schemas) -%}
  {% set information_schema = 'SYS.INFORMATION_SCHEMA'%}
  {% set query %}
      with tables as (

          select
              table_catalog as `table_database`,
              table_schema as `table_schema`,
              table_name as `table_name`,
              table_type as `table_type`,


              'Row Count' as `stats:row_count:label`,
              row_count as `stats:row_count:value`,
              'An approximate count of rows in this table' as `stats:row_count:description`,
              (row_count is not null) as `stats:row_count:include`,

              'Approximate Size' as `stats:bytes:label`,
              bytes as `stats:bytes:value`,
              'Approximate size of the table as reported by clickzetta' as `stats:bytes:description`,
              (bytes is not null) as `stats:bytes:include`,

              'Last Modified' as `stats:last_modified:label`,
              cast(last_modify_time as string) as `stats:last_modified:value`,
              'The timestamp for last update/change' as `stats:last_modified:description`,
              (last_modify_time is not null and table_type='MANAGED_TABLE') as `stats:last_modified:include`

          from {{ information_schema }}.tables
          where delete_time is null
      ),

      columns as (

          select
              table_catalog as `table_database`,
              table_schema as `table_schema`,
              table_name as `table_name`,

              column_name as `column_name`,
              column_id as `column_index`,
              data_type as `column_type`,
              comment as `column_comment`

          from {{ information_schema }}.columns
          where delete_time is null
      )

select *
from tables
         join columns using (`table_database`, `table_schema`, `table_name`)
where (
          {%- for schema in schemas -%}
          upper(`table_schema`) = upper('{{ schema }}'){%- if not loop.last %} or {% endif -%}
          {%- endfor -%}
          )
order by `column_index`
    {%- endset -%}

  {{ return(run_query(query)) }}

{%- endmacro %}
