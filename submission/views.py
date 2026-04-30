from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy
from django.views.generic import UpdateView
import re

from submission.forms import BallotForm, BallotSectionForm, CaptainsMeetingForm, CharacterPronounsForm, \
    CaptainsMeetingSectionForm, ParadigmForm, ParadigmPreferenceItemForm, SpiritForm
from submission.models.ballot import Ballot
from submission.models.spirit import Spirit
from submission.models.captains_meeting import CaptainsMeeting
from submission.models.character import CharacterPronouns, Character
from submission.models.paradigm import ParadigmPreference, ParadigmPreferenceItem, Paradigm
from submission.models.section import BallotSection, Section, SubSection, CaptainsMeetingSection
from tabeasy.utils.mixins import PassRequestToFormViewMixin
from tabeasy.utils.obfuscation import decode_int
from tourney.models import Judge
from tourney.models.team import Team
from django.contrib.auth.decorators import user_passes_test

try:
    from tabeasy_secrets.secret import str_int
except ImportError:
    str_int = decode_int


def build_speaker_pairs(section_forms):
    grouped = {}
    for section_form in section_forms:
        if not section_form:
            continue
        subsection = section_form[0].init_subsection
        match = re.search(r"Speaker\s*(\d+)", f"{subsection.section.name} {subsection.name}", re.IGNORECASE)
        speaker_num = int(match.group(1)) if match else ((subsection.sequence + 1) // 2)
        grouped.setdefault(speaker_num, {"speaker_num": speaker_num, "P": None, "D": None})
        grouped[speaker_num][subsection.side] = section_form
    return [grouped[key] for key in sorted(grouped)]


def get_primary_subsection(section):
    return section.subsections.order_by('sequence', 'pk').first()


def get_predetermined_speaker(captains_meeting, subsection):
    match = re.search(r"Speaker (\d+)", subsection.section.name)
    if not match:
        return None
    speaker_index = int(match.group(1)) - 1
    if speaker_index not in (0, 1):
        return None
    team = captains_meeting.round.p_team if subsection.side == 'P' else captains_meeting.round.d_team
    if not team:
        return None
    competitors = list(team.competitors.order_by('id'))
    if len(competitors) <= speaker_index:
        return None
    return competitors[speaker_index]


def apply_predetermined_speakers(captains_meeting):
    tournament = captains_meeting.round.pairing.tournament
    if not tournament.predetermined_speakers:
        return
    for section in Section.objects.filter(tournament=tournament).all():
        match = re.search(r"Speaker (\d+)", section.name)
        if not match:
            continue
        for subsection in section.subsections.all():
            competitor = get_predetermined_speaker(captains_meeting, subsection)
            if competitor:
                CaptainsMeetingSection.objects.update_or_create(
                    captains_meeting=captains_meeting,
                    subsection=subsection,
                    defaults={'competitor': competitor},
                )
    if not captains_meeting.submit:
        captains_meeting.submit = True
        captains_meeting.save(update_fields=['submit'])


class BallotUpdateView(LoginRequiredMixin, UserPassesTestMixin, PassRequestToFormViewMixin, UpdateView):
    model = Ballot
    template_name = "tourney/ballot.html"
    form_class = BallotForm
    permission_denied_message = 'You are not allowed to view this ballot.'

    def test_func(self):
        self.ballot = get_object_or_404(Ballot, pk=str_int(self.kwargs['encrypted_pk']))
        if self.request.user.is_staff:
            return True
        user_judge = getattr(self.request.user, "judge", None)
        if self.request.user.is_judge and user_judge and self.ballot.judge != user_judge:
            return False
        user_team = getattr(self.request.user, "team", None)
        if self.request.user.is_team and user_team and user_team not in self.ballot.round.teams:
            return False
        return True

    def get_object(self, queryset=None):
        return Ballot.objects.get(pk=str_int(self.kwargs['encrypted_pk']))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tournament = self.object.round.pairing.tournament
        is_team_reader = self.request.user.is_team and not self.request.user.is_staff
        context['show_ballot_scores'] = not is_team_reader or tournament.publish_ballot_scores
        context['show_ballot_comments'] = True
        context['section_forms'] = []
        if BallotSection.objects.filter(ballot=self.object).exists():
            for section in Section.objects.filter(tournament=self.object.judge.user.tournament).all():
                context['section_forms'].append(
                    sorted([BallotSectionForm(instance=ballot_section,
                                       subsection=ballot_section.subsection,
                                       prefix=ballot_section.subsection.__str__(),
                                       request=self.request)
                     for ballot_section in
                     BallotSection.objects.filter(ballot=self.object, subsection__section=section).all()
                     ],key= lambda x: x.init_subsection.sequence)
                )
        else:
            for section in Section.objects.filter(tournament=self.object.judge.user.tournament).all():
                context['section_forms'].append(
                    sorted([BallotSectionForm(subsection=subsection, ballot=self.object,
                                      prefix=subsection.__str__(),
                                      request=self.request)
                    for subsection in
                    SubSection.objects.filter(section=section).all()],
                    key= lambda x: x.init_subsection.sequence)
                )

        context['section_forms'] = sorted(context['section_forms'],
                                    key= lambda x: x[0].init_subsection.sequence)
        context['speaker_pairs'] = build_speaker_pairs(context['section_forms'])
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden()
        self.object = self.get_object()
        form = self.get_form()
        section_forms = []
        if BallotSection.objects.filter(ballot=self.object).exists():
            for section in Section.objects.filter(tournament=self.object.judge.user.tournament).all():
                section_forms.append(
                    sorted([BallotSectionForm(request.POST, instance=ballot_section,
                                       subsection=ballot_section.subsection,
                                       prefix=ballot_section.subsection.__str__(),
                                       request=self.request)
                     for ballot_section in
                     BallotSection.objects.filter(ballot=self.object, subsection__section=section).all()
                     ], key= lambda x: x.init_subsection.sequence)
                )
        else:
            for section in Section.objects.filter(tournament=self.object.judge.user.tournament).all():
                section_forms.append(
                    sorted([BallotSectionForm(request.POST, subsection=subsection, ballot=self.object,
                                      prefix=subsection.__str__(), request=self.request)
                     for subsection in
                     SubSection.objects.filter(section=section).all()],
                    key= lambda x: x.init_subsection.sequence)
                )
        section_forms = sorted(section_forms, key=lambda x: x[0].init_subsection.sequence)
        is_valid = True
        for section in section_forms:
            for subsection_form in section:
                if not subsection_form.is_valid():
                    is_valid = False
                # if subsection_form.cleaned_data.get('score') == 0:
                #     subsection_form.errors['zero'] = f'You cannot score a 0 for {subsection_form.instance}!'
                #     is_valid = False
        if not form.is_valid():
            is_valid = False
        if is_valid:
            return self.form_valid(form, section_forms)
        else:
            return self.form_invalid(form, section_forms)

    def form_valid(self, form, section_forms):
        for section in section_forms:
            for subsection_form in section:
                subsection_form.save()
        response = super().form_valid(form)
        if self.object.submit:
            from tourney.views import finalize_pending_byebuster_exclusions
            finalize_pending_byebuster_exclusions(self.object.round.pairing.tournament)
        return response

    def form_invalid(self, form, section_forms):
        context = self.get_context_data()
        context['section_forms'] = section_forms
        context['speaker_pairs'] = build_speaker_pairs(section_forms)
        return self.render_to_response(context)

    def get_success_url(self):
        if self.ballot.submit:
            for opponent in self.ballot.round.p_team.opponents():
                opponent.save()
            for opponent in self.ballot.round.d_team.opponents():
                opponent.save()
            self.ballot.round.p_team.save()
            self.ballot.round.d_team.save()
            for opponent in self.ballot.round.p_team.opponents():
                opponent.save()
            for opponent in self.ballot.round.d_team.opponents():
                opponent.save()
        return self.request.path


class CaptainsMeetingUpdateView(LoginRequiredMixin, UserPassesTestMixin, PassRequestToFormViewMixin, UpdateView):
    model = CaptainsMeeting
    template_name = "tourney/captains_meeting.html"
    form_class = CaptainsMeetingForm
    permission_denied_message = 'You are not allowed to view this Captains Meeting Form.'

    def test_func(self):
        self.captains_meeting = get_object_or_404(CaptainsMeeting, pk=str_int(self.kwargs['encrypted_pk']))
        if self.request.user.is_staff:
            return True
        user_team = getattr(self.request.user, "team", None)
        if self.request.user.is_team and user_team and user_team not in self.captains_meeting.round.teams:
            return False
        user_judge = getattr(self.request.user, "judge", None)
        if self.request.user.is_judge and user_judge and user_judge not in self.captains_meeting.round.judges:
            return False
        return True

    def get_object(self, queryset=None):
        return CaptainsMeeting.objects.get(pk=str_int(self.kwargs['encrypted_pk']))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pronouns_forms'] = []
        context['predetermined_speakers_locked'] = (
            self.object.round.pairing.tournament.predetermined_speakers
            and self.request.user.is_team
            and not self.request.user.is_staff
        )

        context['section_forms'] = []
        apply_predetermined_speakers(self.object)
        if CaptainsMeetingSection.objects.filter(captains_meeting=self.object).exists():
            for section in Section.objects.filter(tournament=self.object.round.pairing.tournament).all():
                temp = []
                primary_subsection = get_primary_subsection(section)
                for subsection in CaptainsMeetingSection.objects.filter(captains_meeting=self.object,
                                                          subsection__section=section).all():
                    if primary_subsection and subsection.subsection.pk == primary_subsection.pk:
                        temp.append(
                            CaptainsMeetingSectionForm(instance=subsection,
                                                       captains_meeting=self.object,
                                                       subsection=subsection.subsection,
                                                       prefix=subsection.subsection.__str__(),
                                                       request=self.request)
                        )
                temp = sorted(temp, key= lambda x: x.init_subsection.sequence)
                context['section_forms'].append(temp)
        else:
            for section in Section.objects.filter(tournament=self.object.round.pairing.tournament).all():
                temp = []
                primary_subsection = get_primary_subsection(section)
                for subsection in SubSection.objects.filter(section=section).all():
                    if primary_subsection and subsection.pk == primary_subsection.pk:
                        temp.append(
                            CaptainsMeetingSectionForm(subsection=subsection, captains_meeting=self.object,
                                          prefix=subsection.__str__(), request=self.request)
                        )
                temp = sorted(temp, key=lambda x: x.init_subsection.sequence)
                context['section_forms'].append(temp)
        context['section_forms'] = sorted(context['section_forms'],
                                    key= lambda x: x[0].init_subsection.sequence)

        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden()
        self.object = self.get_object()
        apply_predetermined_speakers(self.object)
        if (
            self.object.round.pairing.tournament.predetermined_speakers
            and request.user.is_team
            and not request.user.is_staff
        ):
            return redirect(self.get_success_url())
        form = self.get_form()
        pronouns_forms = []


        section_forms = []
        if CaptainsMeetingSection.objects.filter(captains_meeting=self.object).exists():
            for section in Section.objects.filter(tournament=self.object.round.pairing.tournament).all():
                temp = []
                primary_subsection = get_primary_subsection(section)
                for subsection in CaptainsMeetingSection.objects.filter(captains_meeting=self.object,
                                                                           subsection__section=section).all():
                    if primary_subsection and subsection.subsection.pk == primary_subsection.pk:
                        temp.append(
                            CaptainsMeetingSectionForm(request.POST, instance=subsection,
                                                       captains_meeting=self.object,
                                                       subsection=subsection.subsection,
                                                       prefix=subsection.subsection.__str__(),
                                                       form=form, request=self.request)
                        )
                temp = sorted(temp, key=lambda x: x.init_subsection.sequence)
                section_forms.append(temp)
        else:
            for section in Section.objects.filter(tournament=self.object.round.pairing.tournament).all():
                temp = []
                primary_subsection = get_primary_subsection(section)
                for subsection in SubSection.objects.filter(section=section).all():
                    if primary_subsection and subsection.pk == primary_subsection.pk:
                        temp.append(
                            CaptainsMeetingSectionForm(request.POST, subsection=subsection,
                                                       captains_meeting=self.object,
                                                       prefix=subsection.__str__(),
                                                       form=form,request=self.request)
                        )
                temp = sorted(temp, key=lambda x: x.init_subsection.sequence)
                section_forms.append(temp)

        section_forms = sorted(section_forms,
                                    key= lambda x: x[0].init_subsection.sequence)

        is_valid = True

        if not form.is_valid():
            is_valid = False
        speeches = []
        for section in section_forms:
            for subsection_form in section:
                if not subsection_form.is_valid():
                    is_valid = False
                elif form.cleaned_data.get('submit'):
                    competitor = subsection_form.cleaned_data.get('competitor')
                    if competitor in speeches:
                        is_valid = False
                        subsection_form.errors['speeches'] = f"{competitor} is assigned to more than one speaker slot."
                    elif competitor:
                        speeches.append(competitor)


        if is_valid:
            return self.form_valid(form, pronouns_forms, section_forms)
        else:
            return self.form_invalid(form, pronouns_forms, section_forms)

    def form_valid(self, form, pronouns_forms, section_forms):
        if self.object.round.pairing.tournament.predetermined_speakers and not self.request.user.is_staff:
            apply_predetermined_speakers(self.object)
            return super().form_valid(form)
        for section in section_forms:
            for subsection_form in section:
                subsection_form.save()
                competitor = subsection_form.instance.competitor
                for subsection in subsection_form.init_subsection.section.subsections.exclude(pk=subsection_form.init_subsection.pk):
                    CaptainsMeetingSection.objects.update_or_create(
                        captains_meeting=subsection_form.init_captains_meeting,
                        subsection=subsection,
                        defaults={"competitor": competitor},
                    )

        return super().form_valid(form)

    def form_invalid(self, form, pronouns_forms, section_forms):
        context = self.get_context_data()
        context['pronouns_forms'] = pronouns_forms
        context['section_forms'] = section_forms
        return self.render_to_response(context)

    def get_success_url(self):
        return reverse_lazy('index')
    


@user_passes_test(lambda u: (u.is_staff or u.is_team))
def edit_spirit(request, team_pk): 
    team = Team.objects.get(pk=team_pk) 
    if not request.user.is_staff and request.user.team != team:
        return redirect('index')
        
    if Spirit.objects.filter(team=team).exists():
        spirit = Spirit.objects.get(team=team)
    else:
        spirit = Spirit.objects.create(team=team)
    
    if request.method == "POST":
        spirit_form = SpiritForm(request.POST, instance=spirit, request=request)
        if spirit_form.is_valid():
            spirit_form.save()
            for opponent in team.opponents():
                opponent.save()
            return redirect('index')
        else: 
            spirit_form.errors['error'] = "The form did not save because of some errors"
            return render(request, 'tourney/spirit.html', {'form': spirit_form, 
                                                    'team': team})
    else: 
        spirit_form = SpiritForm(instance=spirit, request=request)
    
    
    return render(request, 'tourney/spirit.html', {'form': spirit_form, 
                                                    'team': team})


def edit_paradigm(request, judge):
    judge = Judge.objects.get(user__username=judge)
    if Paradigm.objects.filter(judge=judge).exists():
        paradigm = Paradigm.objects.get(judge=judge)
    else:
        paradigm = Paradigm.objects.create(judge=judge)

    if request.method == "POST":
        paradigm_form = ParadigmForm(request.POST, instance=paradigm)
        if ParadigmPreferenceItem.objects.filter(paradigm=paradigm).exists():
            paradigm_preference_item_forms = [
                ParadigmPreferenceItemForm(request.POST, instance=each, prefix=each.__str__())
                for each in ParadigmPreferenceItem.objects.filter(paradigm=paradigm).all()
            ]
        else:
            paradigm_preference_item_forms = [
                ParadigmPreferenceItemForm(request.POST, paradigm=paradigm, paradigm_preference=each,
                                           prefix=each.__str__())
                for each in ParadigmPreference.objects.all()
            ]

        is_true = True

        if paradigm_form.is_valid():
            paradigm_form.save()
        else:
            is_true = False

        for form in paradigm_preference_item_forms:
            if form.is_valid():
                form.save()
            else:
                is_true = False

        if is_true:
            return redirect('index')

    else:
        paradigm_form = ParadigmForm(instance=paradigm)
        if ParadigmPreferenceItem.objects.filter(paradigm=paradigm).exists():
            paradigm_preference_item_forms = [
                ParadigmPreferenceItemForm(instance=each, prefix=each.__str__())
                for each in ParadigmPreferenceItem.objects.filter(paradigm=paradigm).all()
            ]
        else:
            paradigm_preference_item_forms = [
                ParadigmPreferenceItemForm(paradigm=paradigm, paradigm_preference=each,
                                           prefix=each.__str__())
                for each in ParadigmPreference.objects.all()
            ]

    return render(request, 'tourney/paradigm.html', {'judge': judge,
                                                     'paradigm_form':paradigm_form,
                                                     'forms': paradigm_preference_item_forms})
