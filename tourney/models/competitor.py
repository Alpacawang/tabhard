from django.apps import apps
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
        self.p_att = self._speaker_score_for_side('P')
        self.d_att = self._speaker_score_for_side('D')

    def calc_wit_individual_score(self):
        self.p_wit = 0
        self.d_wit = 0

    def _counted_ballot_sections(self):
        tournament = self.team.user.tournament
        ballot_section_model = apps.get_model('submission', 'BallotSection')
        captains_meeting_section_model = apps.get_model('submission', 'CaptainsMeetingSection')
        assigned_sections = captains_meeting_section_model.objects.filter(
            competitor=self,
            subsection__role='att',
        ).values_list('captains_meeting__round_id', 'subsection_id')
        total = 0
        for round_id, subsection_id in assigned_sections:
            ballot_sections = ballot_section_model.objects.filter(
                ballot__submit=True,
                ballot__round_id=round_id,
                subsection_id=subsection_id,
            ).select_related('ballot__round')
            for ballot_section in ballot_sections:
                ballot = ballot_section.ballot
                if tournament.is_elim_round(ballot.round.pairing.round_num):
                    continue
                if tournament.judges == 1 and ballot.judge != ballot.round.presiding_judge:
                    continue
                if tournament.judges == 2 and ballot.judge == ballot.round.extra_judge:
                    continue
                total += ballot_section.score or 0
        return total

    def _speaker_score_for_side(self, side):
        tournament = self.team.user.tournament
        ballot_section_model = apps.get_model('submission', 'BallotSection')
        captains_meeting_section_model = apps.get_model('submission', 'CaptainsMeetingSection')
        assigned_sections = captains_meeting_section_model.objects.filter(
            competitor=self,
            subsection__role='att',
            subsection__side=side,
        ).values_list('captains_meeting__round_id', 'subsection_id')
        total = 0
        for round_id, subsection_id in assigned_sections:
            ballot_sections = ballot_section_model.objects.filter(
                ballot__submit=True,
                ballot__round_id=round_id,
                subsection_id=subsection_id,
            ).select_related('ballot__round')
            for ballot_section in ballot_sections:
                ballot = ballot_section.ballot
                if tournament.is_elim_round(ballot.round.pairing.round_num):
                    continue
                if tournament.judges == 1 and ballot.judge != ballot.round.presiding_judge:
                    continue
                if tournament.judges == 2 and ballot.judge == ballot.round.extra_judge:
                    continue
                total += ballot_section.score or 0
        return total

    def calc_total_score(self):
        self.total_score = self._counted_ballot_sections()

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
