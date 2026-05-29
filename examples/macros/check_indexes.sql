{% macro check_indexes(relation_name, expected_indexes) %}
{#
  验证表上是否存在指定的索引。
  expected_indexes: list of {name: str, type: str}
    type 值：'bloom_filter' 或 'inverted'

  用法：
    {{ check_indexes(
        relation_name = target.schema ~ '.my_table',
        expected_indexes = [
            {'name': 'example_my_table_id_bloomfilter_idx', 'type': 'bloom_filter'},
            {'name': 'example_my_table_status_inverted_idx', 'type': 'inverted'}
        ]
    ) }}
#}

{%- set ns = namespace(missing=[]) -%}

{%- if execute -%}
  {%- set result = run_query("show index from " ~ relation_name) -%}
  {%- set existing = {} -%}
  {%- for row in result.rows -%}
    {%- set row_dict = dict(zip(result.column_names | map('lower') | list, row)) -%}
    {%- do existing.update({row_dict['index_name']: row_dict['index_type']}) -%}
  {%- endfor -%}

  {%- for expected in expected_indexes -%}
    {%- if expected.name not in existing or existing[expected.name] != expected.type -%}
      {%- do ns.missing.append(expected) -%}
    {%- endif -%}
  {%- endfor -%}
{%- endif -%}

{%- if ns.missing | length == 0 -%}
select 1 where 1=0
{%- else -%}
  {%- for m in ns.missing -%}
select
    '{{ relation_name }}'  as relation,
    '{{ m.name }}'         as expected_index,
    '{{ m.type }}'         as expected_type,
    'index not found'      as reason
    {%- if not loop.last %} union all {% endif %}
  {%- endfor -%}
{%- endif -%}

{% endmacro %}
