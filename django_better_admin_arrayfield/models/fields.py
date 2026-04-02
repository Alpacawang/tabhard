from django.contrib.postgres.fields import ArrayField as PostgresArrayField


class ArrayField(PostgresArrayField):
    """Compatibility wrapper around Django's built-in Postgres ArrayField."""

