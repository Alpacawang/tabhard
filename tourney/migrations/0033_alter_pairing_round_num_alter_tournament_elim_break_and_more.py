import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tourney", "0032_tournament_elim_break_tournament_prelim_rounds_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pairing",
            name="round_num",
            field=models.IntegerField(
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(9),
                ]
            ),
        ),
        migrations.AlterField(
            model_name="tournament",
            name="elim_break",
            field=models.CharField(
                choices=[
                    ("none", "No Elimination Rounds"),
                    ("round32", "Round of 32"),
                    ("round16", "Round of 16"),
                    ("quarters", "Quarters"),
                    ("semis", "Semis"),
                    ("finals", "Finals"),
                ],
                default="none",
                help_text="How far should the break clear before finals?",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="tournament",
            name="p_choice",
            field=models.CharField(
                choices=[("Petitioner", "Petitioner"), ("Applicant", "Applicant")],
                help_text="Petitioner side label",
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name="tournament",
            name="prelim_rounds",
            field=models.IntegerField(
                default=4,
                help_text="How many preliminary rounds should be tabbed before elimination rounds?",
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(4),
                ],
            ),
        ),
    ]
