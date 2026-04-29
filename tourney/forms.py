from django import forms
from django.core.exceptions import ValidationError
from django.forms import MultipleChoiceField
from django.forms.models import ModelChoiceIterator, BaseInlineFormSet

from tabeasy.settings import DEBUG
from tourney.models import Tournament
from tourney.models.judge import Judge
from tourney.models.round import Pairing, Round
from tourney.models.team import Team
from tourney.models.competitor import Competitor

BOOL_CHOICES = ((True, 'Yes'), (False, 'No'))
INT_CHOICES = [(i,i) for i in range(11)]

public_choices = [
    ( True,'Ballot Scores'),
    ( False, 'Comments Only')
]


def get_judge_availability_choices(tournament=None):
    total_rounds = tournament.total_rounds if tournament else 4
    total_rounds = min(max(total_rounds, 1), 9)
    return [
        (f'available_round{i}', tournament.get_round_label(i) if tournament else f'Prelim {i}')
        for i in range(1, total_rounds + 1)
    ]

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['team_name', 'school', 'byebuster']


class TournamentForm(forms.ModelForm):
    judges = forms.TypedChoiceField(
        choices=[(1, '1'), (2, '2'), (3, '3')],
        coerce=int,
        label='Ballots Counted',
        help_text='How many ballots should count toward results?',
    )
    required_judges = forms.TypedChoiceField(
        choices=[(1, '1'), (2, '2'), (3, '3')],
        coerce=int,
        label='Minimum Judges Assigned',
        help_text='How many judges must be assigned before a round can be finalized?',
    )

    class Meta:
        model = Tournament
        fields = '__all__'
        exclude = ['split_division', 'rank_nums', 'conflict_other_side']
    
    publish_ballot_scores = forms.ChoiceField(choices = public_choices, label="Do you want to publish ballot scores or just comments?", initial='', widget=forms.Select())

    def __init__(self, *args, **kwargs):
        super(TournamentForm, self).__init__(*args, **kwargs)
        for round_num in range(1, 10):
            field_name = f'max_judges_round{round_num}'
            if field_name in self.fields:
                self.fields[field_name].widget = forms.Select(choices=[(1, '1'), (2, '2'), (3, '3')])
                self.fields[field_name].label = f'Round {round_num}'
                self.fields[field_name].help_text = ''

    def clean(self):
        cleaned_data = super().clean()
        counted = cleaned_data.get('judges') or 1
        required = cleaned_data.get('required_judges') or 1
        team_size = cleaned_data.get('team_size')
        predetermined_speakers = cleaned_data.get('predetermined_speakers')
        total_rounds = cleaned_data.get('prelim_rounds', self.instance.prelim_rounds if self.instance.pk else 4)
        elim_break = cleaned_data.get('elim_break', self.instance.elim_break if self.instance.pk else 'none')
        if predetermined_speakers and team_size == 3:
            self.add_error('predetermined_speakers', 'Predetermined speakers cannot be enabled for 3-person teams.')
        elim_counts = {
            'none': 0,
            'finals': 1,
            'semis': 2,
            'quarters': 3,
            'round16': 4,
            'round32': 5,
        }
        total_rounds += elim_counts.get(elim_break, 0)
        for round_num in range(1, total_rounds + 1):
            max_judges = cleaned_data.get(f'max_judges_round{round_num}') or 1
            if counted > max_judges:
                self.add_error(f'max_judges_round{round_num}', 'Max judges must be at least as high as ballots counted.')
            if required > max_judges:
                self.add_error(f'max_judges_round{round_num}', 'Max judges must be at least as high as minimum judges assigned.')
        return cleaned_data


class CreateTournamentForm(TournamentForm):
    class Meta(TournamentForm.Meta):
        exclude = TournamentForm.Meta.exclude + [
            'division_team_num',
            'required_judges',
            'max_judges_round1',
            'max_judges_round2',
            'max_judges_round3',
            'max_judges_round4',
            'max_judges_round5',
            'max_judges_round6',
            'max_judges_round7',
            'max_judges_round8',
            'max_judges_round9',
        ]

    def save(self, commit=True):
        tournament = super().save(commit=False)
        tournament.required_judges = tournament.judges
        for round_num in range(1, 10):
            setattr(tournament, f'max_judges_round{round_num}', tournament.judges)
        if commit:
            tournament.save()
        return tournament


    
class JudgeForm(forms.ModelForm):
    availability = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Judge
        fields = ['preside']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        tournament = kwargs.pop('tournament', None)
        super(JudgeForm, self).__init__(*args, **kwargs)
        if tournament is None:
            if getattr(self.instance, 'user_id', None) and getattr(self.instance.user, 'tournament', None):
                tournament = self.instance.user.tournament
            elif self.request and getattr(self.request.user, 'tournament', None):
                tournament = self.request.user.tournament
            elif self.data and self.data.get('tournament'):
                try:
                    tournament = Tournament.objects.get(pk=self.data.get('tournament'))
                except (Tournament.DoesNotExist, TypeError, ValueError):
                    tournament = None
        availability_choices = get_judge_availability_choices(tournament)
        self.fields['availability'].choices = availability_choices
        self.fields['availability'].label = "Which round(s) would you like to judge?"
        initial_availability = []
        for field_name, _ in availability_choices:
            if getattr(self.instance, field_name, False):
                initial_availability.append(field_name)
        self.fields['availability'].initial = initial_availability

    def save(self, commit=True):
        m = super(JudgeForm, self).save(commit=False)
        selected = set(self.cleaned_data.get('availability') or [])
        for field_name in Judge.availability_field_names():
            if field_name in selected:
                setattr(m, field_name, True)
            else:
                setattr(m, field_name, False)
        if commit:
            m.save()
        return m


class CompetitorForm(forms.ModelForm):
    class Meta:
        model = Competitor
        fields = '__all__'
        exclude = ['name', 'pronouns']


class PairingSubmitForm(forms.ModelForm):
    class Meta:
        model = Pairing
        fields = ['team_submit', 'final_submit', 'publish']
        

class RoundForm(forms.ModelForm):
    class Meta:
        model = Round
        fields = '__all__'
        exclude = ['pairing','courtroom']
        # widgets = {
        #     'p_team': SearchableSelect(model='Round', search_field='p_team', limit=10),
        #     'd_team': SearchableSelect(model='Round', search_field='d_team', limit=10)
        # }
    # p_team = ajax_select_fields.AutoCompleteSelectField('p_team')


    def __init__(self, *args, **kwargs):
        pairing = kwargs.pop('pairing', None)
        self.other_formset = kwargs.pop('other_formset', None)
        self.request = kwargs.pop('request', None)
        self.waive_conflicts = kwargs.pop('waive_conflicts', False)
        tournament = self.request.user.tournament
        super(RoundForm, self).__init__(*args, **kwargs)
        if pairing == None:
            self.fields['p_team'].queryset = Team.objects.all()
            self.fields['d_team'].queryset = Team.objects.all()
            self.fields['presiding_judge'].queryset = Judge.objects.filter(preside__gt=0)
        else:
            max_judges = pairing.tournament.get_max_judges_for_round(pairing.round_num)
            # if not pairing.final_submit:
            for field in self.fields:
                self.fields[field].required = False
            if pairing.division:
                self.fields['p_team'].queryset = Team.objects.filter(user__tournament=tournament,
                                                                     division=pairing.division)
                self.fields['d_team'].queryset = Team.objects.filter(user__tournament=tournament,
                                                                     division=pairing.division)
            else:
                self.fields['p_team'].queryset = Team.objects.filter(user__tournament=tournament)
                self.fields['d_team'].queryset = Team.objects.filter(user__tournament=tournament)
            available_judges_pk = [judge.pk for judge in Judge.objects.filter(user__tournament=tournament)
                                   if judge.get_availability(pairing.round_num)]
            self.fields['presiding_judge'].queryset = \
                Judge.objects.filter(pk__in=available_judges_pk, preside__gt=0,
                                     checkin=True).order_by('checkin','user__username')
            self.fields['scoring_judge'].queryset = Judge.objects.filter(pk__in=available_judges_pk,
                                                                         checkin=True).order_by('checkin','user__username')
            self.fields['extra_judge'].queryset = Judge.objects.filter(pk__in=available_judges_pk,
                                                                         checkin=True).order_by('checkin',
                                                                                                'user__username')
            if max_judges < 2:
                self.fields['scoring_judge'].widget = forms.HiddenInput()
                self.fields['extra_judge'].widget = forms.HiddenInput()
            elif max_judges < 3:
                self.fields['extra_judge'].widget = forms.HiddenInput()

    def _post_clean(self):
        self.instance._waive_conflicts = self.waive_conflicts
        super()._post_clean()

    def clean(self):
        cleaned_data = super().clean()
        errors = []
        max_judges = self.instance.pairing.tournament.get_max_judges_for_round(self.instance.pairing.round_num)
        required_judges = max(1, min(self.instance.pairing.tournament.required_judges, max_judges))

        if max_judges < 2:
            cleaned_data['scoring_judge'] = None
            cleaned_data['extra_judge'] = None
            self.instance.scoring_judge = None
            self.instance.extra_judge = None
        elif max_judges < 3:
            cleaned_data['extra_judge'] = None
            self.instance.extra_judge = None

        if self.instance.pairing.final_submit == True:
            if required_judges >= 1 and not cleaned_data.get('presiding_judge'):
                errors.append(f"You haven't assigned presiding judge for {self.instance} yet before checking for conflicts")
            if required_judges >= 2 and not cleaned_data.get('scoring_judge'):
                errors.append(f"You haven't assigned scoring judge for {self.instance} yet before checking for conflicts")
            if required_judges >= 3 and not cleaned_data.get('extra_judge'):
                errors.append(f"You haven't assigned extra judge for {self.instance} yet before checking for conflicts")


        # check for judges
        if self.other_formset != None and self.instance.pairing.final_submit:
            form_judges = [cleaned_data.get('presiding_judge'), cleaned_data.get('scoring_judge'),
                           cleaned_data.get('extra_judge')]
            for form in self.other_formset:
                if form.cleaned_data == {} and not DEBUG:
                    raise ValidationError('You don\'t have enough rounds.')
                elif form.cleaned_data == {} and DEBUG:
                    continue

                other_form_judges = [form.cleaned_data.get('presiding_judge'),
                                     form.cleaned_data.get('scoring_judge'), form.cleaned_data.get('extra_judge')]
                # #check if assigned in another division this should be done on the form level
                for judge in form_judges:
                    if judge and judge in other_form_judges:
                        errors.append(f"{other_form_judges} {form_judges} {judge} already assigned in {form.instance.pairing.division}")

        if errors != []:
            raise ValidationError(errors)


    def save(self, commit=True):
        would_save = False
        for k, v in self.instance.__dict__.items():
            if k in ['p_team_id','d_team_id','presiding_judge_id','scoring_judge_id'] and v != None:
                would_save = True
        if would_save:
            super().save()



class PairingFormSet(BaseInlineFormSet):

    # def __init__(self, *args, **kwargs):
    #     self.other_form = kwargs.pop('other_form')
    #     super(PairingFormSet, self).__init__(*args, **kwargs)


    def clean(self):
        super().clean()
        if any(self.errors):
            return
        existing_judges = []
        existing_teams = []
        errors = []

        if self.instance.team_submit or self.instance.final_submit:
            for form in self.forms:
                if self.can_delete and self._should_delete_form(form):
                    continue
                if form.cleaned_data == {} and not DEBUG:
                    raise ValidationError('You don\'t have enough rounds.')
                elif form.cleaned_data == {} and DEBUG:
                    continue

                teams = [form.cleaned_data.get('p_team'),form.cleaned_data.get('d_team')]
                for team in teams:
                    if team in existing_teams:
                        errors.append(f'{team} used twice!')
                    existing_teams.append(team)


        if self.instance.final_submit:
            for form in self.forms:
                if self.can_delete and self._should_delete_form(form):
                    continue
                if form.cleaned_data == {}:
                    continue
                form_judges = [form.cleaned_data.get('presiding_judge'),
                               form.cleaned_data.get('scoring_judge'), form.cleaned_data.get('extra_judge')]
                for judge in form_judges:
                    if judge:
                        if judge in existing_judges:
                            errors.append(f'{judge} used twice!')
                        existing_judges.append(judge)

        if errors != []:
            raise ValidationError(errors)


class CustomModelChoiceIterator(ModelChoiceIterator):
    def choice(self, obj):
        return (self.field.prepare_value(obj),
                self.field.label_from_instance(obj), obj)
        # return obj

class CustomModelChoiceField(forms.ModelMultipleChoiceField):
    def _get_choices(self):
        if hasattr(self, '_choices'):
            return self._choices
        return CustomModelChoiceIterator(self)

    def _set_choices(self, value):
        self._choices = value
        self.widget.choices = value

    choices = property(_get_choices, _set_choices)

class UpdateConflictForm(forms.ModelForm):
    class Meta:
        model = Judge
        fields = ['conflicts']
    #
    # user = forms.Select()
    # conflicts_queryset = ( (team, team.school) for team in Team.objects.all() )
    conflicts = CustomModelChoiceField(
        queryset=Team.objects.all(),
        widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(UpdateConflictForm, self).__init__(*args, **kwargs)
        self.fields['conflicts'].queryset = Team.objects.filter(user__tournament=self.request.user.tournament)


class UpdateJudgeFriendForm(forms.ModelForm):
    class Meta:
        model = Judge
        fields = ['judge_friends']

    judge_friends = forms.ModelMultipleChoiceField(
        queryset=Judge.objects.all(),
        widget=forms.CheckboxSelectMultiple
    )
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(UpdateJudgeFriendForm, self).__init__(*args, **kwargs)
        self.fields['judge_friends'].queryset = Judge.objects.filter(user__tournament=self.request.user.tournament)


class CheckinJudgeForm(forms.Form):

    checkins = forms.ModelMultipleChoiceField(
        queryset=Judge.objects.all(),
        widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, **kwargs):
        round_num = kwargs.pop('round_num', None)
        request = kwargs.pop('request', None)

        super(CheckinJudgeForm, self).__init__(*args, **kwargs)
        if request and getattr(request.user, 'tournament', None) and round_num:
            self.fields['checkins'].label = f"Which judges are checked in for {request.user.tournament.get_round_label(round_num)}?"
        available_judges_pk = [judge.pk for judge in Judge.objects.filter(user__tournament=request.user.tournament)
                               if judge.get_availability(round_num)]
        self.fields['checkins'].queryset = Judge.objects.filter(checkin=False, pk__in=available_judges_pk)



class CompetitorPronounsForm(forms.ModelForm):
    class Meta:
        model = Competitor
        fields = ['pronouns']
