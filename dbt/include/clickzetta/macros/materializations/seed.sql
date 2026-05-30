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
    Load seed data via PUT + COPY INTO:
    1. adapter.put_seed_file() writes CSV to local temp file and PUTs it to User Volume
       (file I/O must happen in Python; PUT is executed via cursor to avoid query comment
       injection which would break the connector's PUT detection)
    2. COPY INTO loads from User Volume — pure SQL, executed here
    3. REMOVE USER VOLUME FILE cleans up on failure (PURGE=TRUE handles success case)

    COPY INTO handles string-to-type coercion natively for all ClickZetta types
    (timestamp, decimal, bigint, etc.) — no special handling needed.
    This is 10-100x faster than INSERT VALUES for large seed files.
  --#}
  {%- if execute -%}
    {#-- Step 1: write CSV + PUT to User Volume (Python layer, returns filename) --#}
    {%- set tmp_name = adapter.put_seed_file(agate_table) -%}

    {#-- Step 2: COPY INTO from User Volume; PURGE=TRUE removes file on success --#}
    {% call statement('main') %}
      COPY INTO {{ this.render() }} FROM USER VOLUME
      USING CSV OPTIONS('header'='true', 'nullValue'='')
      FILES('{{ tmp_name }}') PURGE=TRUE
    {% endcall %}
  {%- endif -%}

  {{ return("-- seed loaded via COPY INTO: " ~ this.render()) }}
{% endmacro %}
