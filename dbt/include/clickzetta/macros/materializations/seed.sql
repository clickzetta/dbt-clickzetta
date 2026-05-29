{% macro clickzetta__get_binding_char() %}
  {{ return('?' if target.method == 'odbc' else '%s') }}
{% endmacro %}


{% macro clickzetta__reset_csv_table(model, full_refresh, old_relation, agate_table) %}
    {% if old_relation %}
        {{ adapter.drop_relation(old_relation) }}
    {% endif %}
    {% set sql = create_csv_table(model, agate_table) %}
    {{ return(sql) }}
{% endmacro %}


{% macro clickzetta__load_csv_rows(model, agate_table) %}

  {% set batch_size = get_batch_size() %}
  {% set column_override = model['config'].get('column_types', {}) %}

  {#
    Types that require inline literal syntax in ClickZetta INSERT statements.
    Parameterized binding (%s) hangs or fails for these types.
    Canonical ClickZetta names + common aliases all included.
  #}
  {% set inline_type_prefixes = {
    'timestamp':     'TIMESTAMP',
    'timestamp_ltz': 'TIMESTAMP',
    'timestamp_ntz': 'TIMESTAMP_NTZ',
    'date':          'DATE',
    'interval':      'INTERVAL'
  } %}

  {% set statements = [] %}

  {% for chunk in agate_table.rows | batch(batch_size) %}
      {% set bindings = [] %}
      {% set col_inline_prefix = [] %}

      {# Determine per-column inline prefix (empty string = use binding) #}
      {% for col_name in agate_table.column_names %}
          {%- set inferred_type = adapter.convert_type(agate_table, loop.index0) -%}
          {%- set raw_type = column_override.get(col_name, inferred_type) -%}
          {%- set base_type = (raw_type | lower).split('(')[0] | replace(' ', '_') | trim -%}
          {%- set prefix = inline_type_prefixes.get(base_type, '') -%}
          {%- do col_inline_prefix.append(prefix) -%}
      {% endfor %}

      {# Collect bindings only for non-inline columns #}
      {% for row in chunk %}
          {% for i in range(agate_table.column_names | length) %}
              {% if not col_inline_prefix[i] %}
                  {% do bindings.append(row[i]) %}
              {% endif %}
          {% endfor %}
      {% endfor %}

      {% set sql %}
          insert into {{ this.render() }} values
          {% for row in chunk -%}
              ({%- for i in range(agate_table.column_names | length) -%}
                  {%- set col_name = agate_table.column_names[i] -%}
                  {%- set inferred_type = adapter.convert_type(agate_table, i) -%}
                  {%- set type = column_override.get(col_name, inferred_type) -%}
                  {%- set col_val = row[i] -%}
                  {%- set prefix = col_inline_prefix[i] -%}
                  {%- if prefix -%}
                      {%- if col_val is none or col_val == '' -%}
                          null
                      {%- else -%}
                          {{ prefix }} '{{ col_val }}'
                      {%- endif -%}
                  {%- else -%}
                      cast({{ get_binding_char() }} as {{ type }})
                  {%- endif -%}
                  {%- if not loop.last %},{%- endif %}
              {%- endfor -%})
              {%- if not loop.last %},{%- endif %}
          {%- endfor %}
      {% endset %}

      {% do adapter.add_query(sql, bindings=bindings, abridge_sql_log=True) %}

      {% if loop.index0 == 0 %}
          {% do statements.append(sql) %}
      {% endif %}
  {% endfor %}

  {# Return SQL so we can render it out into the compiled files #}
  {{ return(statements[0]) }}
{% endmacro %}
