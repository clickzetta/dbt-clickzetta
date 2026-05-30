{% macro clickzetta__get_binding_char() %}
  {{ return('?' if target.method == 'odbc' else '%s') }}
{% endmacro %}

{% macro clickzetta__get_batch_size() %}
  {{ return(1000) }}
{% endmacro %}

{% macro clickzetta__reset_csv_table(model, full_refresh, old_relation, agate_table) %}
    {% if old_relation %}
        {{ adapter.drop_relation(old_relation) }}
    {% endif %}
    {% set sql = create_csv_table(model, agate_table) %}
    {{ return(sql) }}
{% endmacro %}


{% macro clickzetta__load_csv_rows(model, agate_table) %}
  {#--
    Load seed data via PUT + COPY INTO using adapter.seed_load().

    All steps (write CSV, PUT to User Volume, COPY INTO, cleanup) are handled
    in Python so try/finally guarantees User Volume file cleanup on any failure.
    COPY INTO handles string-to-type coercion natively for all ClickZetta types.
    This is 10-100x faster than INSERT VALUES for large seed files.
  --#}
  {%- if execute -%}
    {%- do adapter.seed_load(this.render(), agate_table) -%}
  {%- endif -%}

  {{ return("-- seed loaded via COPY INTO: " ~ this.render()) }}
{% endmacro %}
