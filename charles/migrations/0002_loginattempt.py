from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charles", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(db_index=True, max_length=150, unique=True)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("last_failed_at", models.DateTimeField(blank=True, null=True)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Login attempt",
                "verbose_name_plural": "Login attempts",
            },
        ),
    ]
