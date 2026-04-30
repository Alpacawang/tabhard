from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from submission.models.captains_meeting import CaptainsMeeting
from tourney.models.team import Team
import re

class Pairing(models.Model):
    tournament = models.ForeignKey('tourney.Tournament', on_delete=models.CASCADE,
                                   related_name='pairings', related_query_name='pairing', null=True)
    division_choices = [('Disney', 'Disney'), ('Universal', 'Universal')]
    division = models.CharField(
        max_length=100,
        choices=division_choices,
        null=True,
        blank=True
    )
    round_num = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(9)])
    team_submit = models.BooleanField(default=False)
    final_submit = models.BooleanField(default=False)
    publish = models.BooleanField(default=False)
    ballots_counted_override = models.IntegerField(null=True, blank=True)

    def get_rounds(self):
        return self.rounds.order_by('courtroom')

    def ballots_counted(self):
        if self.tournament and self.tournament.is_elim_round(self.round_num) and self.ballots_counted_override:
            return self.ballots_counted_override
        return self.tournament.judges if self.tournament else 1


    class Meta:
        unique_together = ('tournament', 'division', 'round_num',)

    def __str__(self):
        label = self.tournament.get_round_label(self.round_num) if self.tournament else f'Round {self.round_num}'
        if self.division != None:
            return f'{label} {self.division}'
        else:
            return f'{label}'

class Round(models.Model):
    pairing = models.ForeignKey(Pairing, on_delete=models.CASCADE, related_name='rounds', related_query_name='round', null=True)
    courtroom = models.CharField(max_length=1, null=True)
    p_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='p_rounds',
                               related_query_name='p_round', null=True)
    d_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='d_rounds',
                               related_query_name='d_round', null=True)
    presiding_judge = models.ForeignKey('Judge', on_delete=models.CASCADE, related_name='presiding_rounds',
                                    related_query_name='presiding_round', null=True)
    scoring_judge = models.ForeignKey('Judge', on_delete=models.CASCADE, related_name='scoring_rounds',
                                    related_query_name='scoring_round', null=True, blank=True)
    extra_judge = models.ForeignKey('Judge', on_delete=models.CASCADE, related_name='extra_rounds',
                                      related_query_name='extra_round', null=True, blank=True)
    additional_judges = models.ManyToManyField(
        'Judge',
        related_name='additional_rounds',
        related_query_name='additional_round',
        blank=True,
    )
    # judge_panel = models.ManyToManyField('Judge', related_name='final_rounds', related_query_name='final_round',
    #                                      null=True, blank=True)

    @property
    def judges(self):
        # if self.judge_panel.count() > 0:
        #     return [self.presiding_judge, self.scoring_judge] + [judge for judge in self.judge_panel.all()]
        # elif \
        if not self.presiding_judge:
            return []
        else:
            judges = [judge for judge in [self.presiding_judge, self.scoring_judge, self.extra_judge] if judge]
            if self.pk:
                judges += list(self.additional_judges.all())
            return judges

    @property
    def teams(self):
        return [self.p_team, self.d_team]

    def __str__(self):
        return f'Round {self.pairing.round_num} Courtroom {self.courtroom}'

    def _apply_predetermined_speakers(self, captains_meeting):
        tournament = self.pairing.tournament if self.pairing else None
        if not tournament or not tournament.predetermined_speakers:
            return

        from submission.models.section import CaptainsMeetingSection, Section

        for section in Section.objects.filter(tournament=tournament).all():
            match = re.search(r"Speaker (\d+)", section.name)
            if not match:
                continue
            speaker_index = int(match.group(1)) - 1
            if speaker_index not in (0, 1):
                continue

            for subsection in section.subsections.all():
                team = self.p_team if subsection.side == 'P' else self.d_team
                if not team:
                    continue
                competitors = list(team.competitors.order_by('id'))
                if len(competitors) <= speaker_index:
                    continue
                CaptainsMeetingSection.objects.update_or_create(
                    captains_meeting=captains_meeting,
                    subsection=subsection,
                    defaults={'competitor': competitors[speaker_index]},
                )

        if not captains_meeting.submit:
            captains_meeting.submit = True
            captains_meeting.save(update_fields=['submit'])


    def clean(self):
        super().clean()
        errors = []
        waive_conflicts = getattr(self, '_waive_conflicts', False)

        is_elim = self.pairing.tournament and self.pairing.tournament.is_elim_round(self.pairing.round_num)

        if self.pairing.team_submit or self.pairing.final_submit:
            if not self.p_team or not self.d_team:
                errors.append('One team did not get an opponent to compete against!')
                raise ValidationError(errors)
            if self.p_team == self.d_team:
                errors.append(f'{self.p_team} can\'t compete against itself!')
            if not is_elim and not waive_conflicts:
                if self.p_team.next_side(self.pairing.round_num) == 'd':
                    errors.append(f"{self.p_team} is supposed to play d this round")
                if self.d_team.next_side(self.pairing.round_num) == 'p':
                    errors.append(f"{self.d_team} is supposed to play p this round")
                for round in self.p_team.p_rounds.all():
                    if round != self and round.pairing != self.pairing and round.d_team == self.d_team:
                        errors.append(f"{self.p_team} and {self.d_team} played each other before")
                if self.pairing.tournament.conflict_other_side:
                    for round in self.p_team.d_rounds.all():
                        if round != self and round.pairing != self.pairing and round.p_team == self.d_team:
                            errors.append(f"{self.p_team} and {self.d_team} played each other before on the same side")

        if self.pairing.final_submit:

            # if self.presiding_judge.preside == 0:
            #     errors.append(f'{self.presiding_judge} can\'t preside')
            round_judges = self.judges
            if len(round_judges) != 0 and len(round_judges) != len(set(round_judges)):
                errors.append(f'assigning one judge for two roles in {self}')


            for judge in round_judges:
                if judge != None:
                    if not judge.get_availability(self.pairing.round_num):
                        errors.append(f"{judge} is not available for Round {self.pairing.round_num}")
                    #check conflict
                    if not waive_conflicts:
                        for team in self.teams:
                            if team in judge.conflicts.all():
                                errors.append(f"{judge} conflicted with team {team}")

                    #check if judged
                    if not waive_conflicts:
                        p_judged, d_judged = judge.judged(self.pairing.round_num)
                        if p_judged or d_judged:
                            if not self.p_team.byebuster and self.p_team in p_judged:
                                errors.append(f"{judge} has judged team {self.p_team}")
                            if not self.d_team.byebuster and self.d_team in d_judged:
                                errors.append(f"{judge} has judged team {self.d_team}")
                            if self.pairing.tournament.conflict_other_side:
                                if not self.p_team.byebuster and self.p_team in d_judged:
                                    errors.append(f"{judge} has judged team {self.p_team}")
                                if not self.d_team.byebuster and self.d_team in p_judged:
                                    errors.append(f"{judge} has judged team {self.d_team}")

        if errors != []:
            raise ValidationError(errors)


    def save(self, *args, **kwargs):
        is_new = self.id is None
        super(Round, self).save(*args, **kwargs)
        captains_meeting = None
        if is_new:
            captains_meeting = CaptainsMeeting.objects.create(round=self)
        tournament = self.pairing.tournament if self.pairing else None
        if tournament and tournament.predetermined_speakers:
            if captains_meeting is None:
                captains_meeting, _ = CaptainsMeeting.objects.get_or_create(round=self)
            self._apply_predetermined_speakers(captains_meeting)
        # if self.pairing.final_submit and not self.pairing.publish:
        #     if not Ballot.objects.filter(round=self).exists():
        #         for judge in self.judges:
        #             Ballot.objects.create(round=self, judge=judge)
        #     else:
        #         for judge in self.judges:
        #             if not Ballot.objects.filter(round=self, judge=judge).exists():
        #                 Ballot.objects.create(round=self, judge=judge)
        #         for ballot in Ballot.objects.filter(round=self).all():
        #             if ballot.judge not in self.judges:
        #                 Ballot.objects.filter(round=self, judge=ballot.judge).delete()
