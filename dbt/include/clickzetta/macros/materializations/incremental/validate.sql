{% macro dbt_clickzetta_validate_get_file_format(raw_file_format) %}
  {#-- Validate the file format #}

  {% set accepted_formats = ['text', 'csv', 'json', 'parquet', 'orc'] %}

  {% set invalid_file_format_msg -%}
    Invalid file format provided: {{ raw_file_format }}
    Expected one of: {{ accepted_formats | join(', ') }}
  {%- endset %}

  {% if raw_file_format not in accepted_formats %}
    {% do exceptions.raise_compiler_error(invalid_file_format_msg) %}
  {% endif %}

  {% do return(raw_file_format) %}
{% endmacro %}


{% macro dbt_clickzetta_validate_get_incremental_strategy(raw_strategy, file_format) %}
  {#-- Validate the incremental strategy #}

  {% set invalid_strategy_msg -%}
    Invalid incremental strategy provided: {{ raw_strategy }}
    Expected one of: 'append', 'merge', 'insert_overwrite'
  {%- endset %}

  {% set invalid_merge_msg -%}
    Invalid incremental strategy provided: {{ raw_strategy }}
    You can only choose this strategy when file_format is set to 'delta' or 'iceberg' or 'hudi'
  {%- endset %}
  {% if raw_strategy not in ['append', 'merge', 'insert_overwrite'] %}
    {% do exceptions.raise_compiler_error(invalid_strategy_msg) %}
  {% endif %}

  {% do return(raw_strategy) %}
{% endmacro %}
