{% macro nullcheck(cols) %}
    {{ return(adapter.dispatch('nullcheck', 'dbt')(cols)) }}
{% endmacro %}

{% macro clickzetta__nullcheck(cols) %}
{%- for col in cols %}

    {% if col.is_string() -%}

    nvl({{col.name}},'') as {{col.name}}

    {%- else -%}

    {{col.name}}

    {%- endif -%}

{%- if not loop.last -%} , {%- endif -%}

{%- endfor -%}
{% endmacro %}