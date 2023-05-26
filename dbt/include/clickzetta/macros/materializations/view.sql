{% materialization view, adapter='clickzetta' -%}
    {{ return(create_or_replace_view()) }}
{%- endmaterialization %}
