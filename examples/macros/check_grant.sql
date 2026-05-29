{% macro check_grant(relation_name, rel_type, privilege, grantee) %}

{%- if grantee.startswith('user:') -%}
  {%- set expected_granted_to = 'USER' -%}
  {%- set expected_grantee_name = grantee[5:] -%}
{%- else -%}
  {%- set expected_granted_to = 'ROLE' -%}
  {%- set expected_grantee_name = grantee -%}
{%- endif -%}

{%- set expected_priv = privilege.upper() -%}
{%- set ns = namespace(found=false) -%}

{%- if execute -%}
  {%- set grants_result = run_query("show grants on " ~ rel_type ~ " " ~ relation_name) -%}
  {%- for row in grants_result.rows -%}
    {%- set row_dict = dict(zip(grants_result.column_names | map('lower') | list, row)) -%}
    {%- if row_dict.get('granted_type', '') == 'PRIVILEGE' -%}
      {%- set row_priv = row_dict.get('privilege', '').split()[0].upper() -%}
      {%- set raw_grantee = row_dict.get('grantee_name', '') -%}
      {%- set row_grantee = raw_grantee.split('.')[-1] if '.' in raw_grantee else raw_grantee -%}
      {%- set row_granted_to = row_dict.get('granted_to', 'ROLE').upper() -%}
      {%- if row_priv == expected_priv and row_grantee == expected_grantee_name and row_granted_to == expected_granted_to -%}
        {%- set ns.found = true -%}
      {%- endif -%}
    {%- endif -%}
  {%- endfor -%}
{%- endif -%}

{%- if ns.found -%}
select 1 where 1=0
{%- else -%}
select
    '{{ relation_name }}'  as relation,
    '{{ privilege }}'      as expected_privilege,
    '{{ grantee }}'        as expected_grantee,
    'grant not found'      as reason
{%- endif -%}

{% endmacro %}
