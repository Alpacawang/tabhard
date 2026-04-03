from django.db import models
from tourney.models import Team

pronoun_choices = [
    ('he', 'he/him'),
    ('she', 'she/her'),
    ('they','they/them'),
    ('ze','ze/hir')
]

class Competitor(models.Model):
    name = models.CharField(max_length=60)
    team = models.ForeignKey(Team,on_delete=models.CASCADE,related_name='competitors',related_query_name='competitor')
    pronouns = models.CharField(max_length=20, choices=pronoun_choices, null=True, blank=True)
    p_att = models.IntegerField(default=0)
    d_att = models.IntegerField(default=0)
    p_wit = models.IntegerField(default=0)
    d_wit = models.IntegerField(default=0)
    total_score = models.IntegerField(default=0)


    def __str__(self):
        if self.pronouns == None:
            return self.name
        else:
            for (i, j) in pronoun_choices:
                if i == self.pronouns:
                    return f"{self.name} ({j})"

    def calc_att_individual_score(self):
        p_total = 0
        d_total = 0
        dict = {
            self.att_rank_1.all(): 5,
            self.att_rank_2.all(): 4,
            self.att_rank_3.all(): 3,
            self.att_rank_4.all(): 2,
        }
        for k, v in dict.items():
            for ballot in k:
                if (self.team.user.tournament.judges == 3) or \
                        (self.team.user.tournament.judges == 2 and ballot.judge != ballot.round.extra_judge) \
                        or (self.team.user.tournament.judges == 1 and ballot.judge == ballot.round.presiding_judge):
                    if ballot.round.p_team == self.team:
                        p_total += v
                    else:
                        d_total += v
        tournament = self.team.user.tournament
        if tournament.individual_award_rank_plus_record:
            p_total += self.team.p_ballots
            d_total += self.team.d_ballots
        self.p_att = p_total
        self.d_att = d_total

    def calc_wit_individual_score(self):
        p_total = 0
        d_total = 0
        dict = {
            self.wit_rank_1.all(): 5,
            self.wit_rank_2.all(): 4,
            self.wit_rank_3.all(): 3,
            self.wit_rank_4.all(): 2,
        }
        for k, v in dict.items():
            for ballot in k:
                if (self.team.user.tournament.judges == 3) or \
                        (self.team.user.tournament.judges == 2 and ballot.judge != ballot.round.extra_judge) \
                        or (self.team.user.tournament.judges == 1 and ballot.judge == ballot.round.presiding_judge):
                    if ballot.round.p_team == self.team:
                        p_total += v
                    else:
                        d_total += v
        tournament = self.team.user.tournament
        if tournament.individual_award_rank_plus_record:
            p_total += self.team.p_ballots
            d_total += self.team.d_ballots
        self.p_wit = p_total
        self.d_wit = d_total

    def calc_total_score(self):
        self.total_score = self.p_att + self.d_att + self.p_wit + self.d_wit

    def __lt__(self, other):
        return self.id < other.id

    class Meta:
        ordering = ['id']

    def save(self, *args, **kwargs):
        if self.pk is None:
            super().save(*args, **kwargs)
            self.calc_wit_individual_score()
            self.calc_att_individual_score()
            self.calc_total_score()
            super().save(update_fields=['p_att', 'd_att', 'p_wit', 'd_wit', 'total_score'])
            return
        self.calc_wit_individual_score()
        self.calc_att_individual_score()
        self.calc_total_score()
        super().save(*args, **kwargs)
