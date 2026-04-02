from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator

p_choices = [
    ('Petitioner', 'Petitioner'),
]

ELIM_BREAK_CHOICES = [
    ('none', 'No Elimination Rounds'),
    ('octas', 'Octas'),
    ('quarters', 'Quarters'),
    ('semis', 'Semis'),
]

# def user_directory_path(instance, filename):
#     # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
#     return "tournament_{0}/{1}".format(instance.id, filename)


class Tournament(models.Model):
    name = models.CharField(max_length=40, help_text='Tournament Name:')
    short_name = models.CharField(max_length=10, help_text='Shortened Tournament Name:',
                                  validators=[RegexValidator(r'^[a-zA-Z0-9_-]+$', 'You can only enter alphanumerics, underscores, and dashes.')])
    wit_nums = models.IntegerField(validators=[MinValueValidator(2), MaxValueValidator(2)], default=2,
                                   help_text='Moot court uses two speakers per side.')
    prelim_rounds = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=4,
        help_text='How many preliminary rounds should be tabbed before elimination rounds?',
    )
    elim_break = models.CharField(
        max_length=20,
        choices=ELIM_BREAK_CHOICES,
        default='none',
        help_text='How far should the break clear before finals?',
    )
    rank_nums = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=5,
                                    help_text='How many competitors do judges rank?')
    p_choice = models.CharField(max_length=40, choices=p_choices,
                                help_text='Petitioner side label')
    publish_ballot_scores = models.BooleanField(default=False,
                                                help_text='Do you want to publish ballot scores or just comments?')
    split_division = models.BooleanField(default=False)
    division_team_num = models.IntegerField(default=10,
                                            help_text='How many teams do you have?')
    individual_award_rank_plus_record = models.BooleanField(default=False,
                                                            help_text='Do you include the team\'s record when calculating individual awards?')
    case = models.URLField(max_length=200, null=True, blank=True,
                           help_text='Case Link:')
    roe = models.URLField(max_length=200, null=True, blank=True,
                          help_text='Rules of Evidence Link:')
    zoom_link = models.URLField(max_length=200, null=True, blank=True,
                                help_text='Zoom Meeting Link (leave blank if not applicable):')
    presiding_judge_script = models.URLField(max_length=200, null=True, blank=True,
                                             help_text='Presiding Judge Script (leave blank if not applicable):')
    hide_comments = models.BooleanField(default=False,
                                        help_text='Do you want to hide comments on ballots?')
    judges = models.IntegerField(default=2,
                                 help_text='How many judges do you count into the result?')
    conflict_other_side = models.BooleanField(default=True)
    hide_captains_meeting = models.BooleanField(
        default=False, help_text='Hide the captains meeting?')
    spirit = models.BooleanField(
        default=False, help_text='Do you want to enable the spirit award functionality?')

    def __str__(self):
        return self.name

    @property
    def elim_round_names(self):
        mapping = {
            'none': [],
            'semis': ['Semis', 'Finals'],
            'quarters': ['Quarters', 'Semis', 'Finals'],
            'octas': ['Octas', 'Quarters', 'Semis', 'Finals'],
        }
        return mapping.get(self.elim_break, [])

    @property
    def total_rounds(self):
        return self.prelim_rounds + len(self.elim_round_names)

    def is_elim_round(self, round_num):
        return round_num > self.prelim_rounds

    def get_round_label(self, round_num):
        if self.is_elim_round(round_num):
            index = round_num - self.prelim_rounds - 1
            if 0 <= index < len(self.elim_round_names):
                return self.elim_round_names[index]
        return f'Prelim {round_num}'

    @property
    def elim_break_size(self):
        return {
            'none': 0,
            'semis': 4,
            'quarters': 8,
            'octas': 16,
        }.get(self.elim_break, 0)
