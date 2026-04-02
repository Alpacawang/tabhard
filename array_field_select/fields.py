from django.contrib.postgres.fields import ArrayField as PostgresArrayField


class ArrayField(PostgresArrayField):
    """Compatibility wrapper for legacy array-field-select imports."""

