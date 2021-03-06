import logging
from enum import IntEnum, unique

from apps.hero_advantages.models import Hero
from apps.hero_abilities.models import Ability

from .exceptions import DoNotUnderstandQuestion, Goodbye
from .question_parser import QuestionParser
from .response_text import (
    AbilityDescriptionResponse, AbilityListResponse, AbilityUltimateResponse,
    AbilityHotkeyResponse, AbilityCooldownResponse, AbilitySpellImmunityResponse,
    SingleHeroCountersResponse, TwoHeroAdvantageResponse, IntroductionResponse,
    DescriptionResponse, SampleQuestionResponse, AbilityDamageTypeResponse,
    MultipleUltimateResponse, SingleHeroAdvantagesResponse,
)


logger = logging.getLogger(__name__)
failed_response_logger = logging.getLogger('failed_response')
feedback_logger = logging.getLogger('feedback')


class InnapropriateContextError(BaseException):
    pass


class ResponseGenerator(object):
    @classmethod
    def respond(cls, question_text, conversation_token=None, user_id=None):
        question = QuestionParser(question_text, user_id)

        context = Context.deserialise(conversation_token)
        try:
            if not context:
                context = Context.get_context_from_question(question)

            response, follow_up_context = context.generate_response(question)
        except DoNotUnderstandQuestion:
            failed_response_logger.warning("%s", question)
            raise

        new_converstaion_token = None
        if follow_up_context:
            new_converstaion_token = follow_up_context.serialise()

        response = "<speak>{}</speak>".format(response)
        return response, new_converstaion_token


class Context(object):
    _can_be_used_for_next_context = False
    _can_respond_to_yes_response = False

    def __init__(self):
        self.useage_count = 0

    def serialise(self):
        # Ensure that we're going to be able deserialise it again!
        assert type(self) in self._context_classes()

        return {
            'context-class': type(self).__name__,
            'useage-count': self.useage_count,
        }

    @staticmethod
    def _context_classes():
        return (
            SingleAbilityContext, AbilityListContext, HeroAdvantageContext, FreshContext,
            IntroductionContext, DescriptionContext, FeedbackContext,
        )

    @classmethod
    def deserialise(cls, data):
        if not data:
            return None
        try:
            klass = next(
                k for k in cls._context_classes()
                if data['context-class'] == k.__name__)
        except StopIteration:
            return None

        result = klass()
        result._deserialise(data)
        return result

    def _deserialise(self, data):
        self.useage_count = data.get('useage-count', 0)  # no get?

    # don't include 'call down' -- that's an ability!
    COOLDOWN_WORDS = ('cool down', 'cooldown', 'called down', 'codon')
    SPELL_IMMUNITY_WORDS = ('spell immunity', 'spell amenity', 'black king', 'king bar', 'bkb')
    DAMAGE_TYPE_WORDS = ('damage', 'magical', 'physical', 'pure')
    COUNTER_WORDS = ('strong', 'against', 'counter', 'counters', 'showing at')
    ABILITY_WORDS = ('abilities', 'spells')
    ULTIMATE_WORDS = ('ultimate', )
    FEEDBACK_WORDS = ('feedback', )

    @classmethod
    def get_context_from_question(cls, question):
        """Returns the context to be used answering the question"""
        if not question.text or question.text == 'talk to true sight':
            return IntroductionContext()

        if len(question.abilities) == 1:
            if question.contains_any_string(
                    cls.COOLDOWN_WORDS + cls.SPELL_IMMUNITY_WORDS + cls.DAMAGE_TYPE_WORDS):
                return SingleAbilityContext()

        if len(question.heroes) == 1:
            if question.contains_any_string(cls.COUNTER_WORDS):
                return HeroAdvantageContext()
            if question.contains_any_string(cls.ULTIMATE_WORDS):
                try:
                    ability = Ability.objects.get(hero=question.heroes[0], is_ultimate=True)
                except Ability.MultipleObjectsReturned:
                    return MultipleUltimateContext()
                return SingleAbilityContext(ability=ability)
            if question.contains_any_string(cls.ABILITY_WORDS):
                return AbilityListContext()
            if question.ability_hotkey:
                ability = Ability.objects.get(
                    hero=question.heroes[0],
                    hotkey=question.ability_hotkey)
                return SingleAbilityContext(ability=ability)

        if len(question.heroes) == 2:
            return HeroAdvantageContext()

        if len(question.abilities) == 1:
            return SingleAbilityContext()

        if len(question.heroes) == 1:
            return HeroAdvantageContext()

        if (
                question.contains_any_string((
                    'help', 'what can you do', 'what do you do', 'how does this work'))
                or question.text == 'what'):
            return DescriptionContext()

        if question.contains_any_string(cls.FEEDBACK_WORDS):
            return FeedbackContext()

        raise DoNotUnderstandQuestion

    def generate_response(self, question):
        try:
            response = self._generate_response_text(question)
        except InnapropriateContextError:
            if self.useage_count == 0:
                # The current context is brand knew, and has just come from
                # get_context_from_question. This should never happen.
                raise

            # The current context is unable to answer the question,
            # let's get a new context from the question itself
            try:
                new_context = Context.get_context_from_question(question)
            except DoNotUnderstandQuestion:
                # The question doesn't include enough to get a new context,
                # But perhaps the response was yes or no and we can respond to that...
                if question.no:
                    return FreshContext().generate_response(question)
                if question.yes and self._can_respond_to_yes_response:
                    return self._yes_response, self
                if question.goodbye:
                    raise Goodbye
                raise
            else:
                return new_context.generate_response(question)

        self.useage_count += 1
        if not response[-1:] in ('.', '?') and not response[-2:] == "?'":
            response += '.'

        if self._can_be_used_for_next_context:
            response = self._add_follow_up_question_to_response(response)
            return response, self
        else:
            return response, None

    def _add_follow_up_question_to_response(self, response):
        if self.useage_count == 1:
            follow_up_question = self._first_follow_up_question
        else:
            follow_up_question = self._second_follow_up_question
        return "{} {}".format(response, follow_up_question)

    def _generate_response_text(self, question):
        raise NotImplemented


class ContextWithBlankFollowUpQuestions(Context):
    """Context which doesn't append a follow up question.

    This may be used when the response itself includes a follow up question.
    """
    _can_be_used_for_next_context = True

    def _add_follow_up_question_to_response(self, response):
        return response


class IntroductionContext(ContextWithBlankFollowUpQuestions):
    def _generate_response_text(self, question):
        if self.useage_count > 0:
            raise InnapropriateContextError
        return IntroductionResponse.respond(user_id=question.user_id)


class DescriptionContext(ContextWithBlankFollowUpQuestions):
    def _generate_response_text(self, question):
        if self.useage_count > 0:
            raise InnapropriateContextError
        return DescriptionResponse.respond(user_id=question.user_id)


class FreshContext(ContextWithBlankFollowUpQuestions):
    """A clean context, which asks the user what they'd like to know, giving sample questions"""
    def _generate_response_text(self, question):
        if self.useage_count > 0:
            if question.no:
                raise Goodbye
            raise InnapropriateContextError
        return SampleQuestionResponse.respond(user_id=question.user_id)


class SingleAbilityContext(Context):
    _can_be_used_for_next_context = True
    _second_follow_up_question = "Anything else?"
    _can_respond_to_yes_response = True
    _first_follow_up_question = "Anything else you'd like to know about it?"

    def __init__(self, ability=None):
        super().__init__()
        self.ability = ability

    @property
    def _yes_response(self):
        return (
            "What would you like to know? "
            "You could ask about the cooldown, damage type, or whether {} goes through BKB."
            "".format(self.ability.name))

    def serialise(self):
        result = super().serialise()
        result['ability'] = self.ability.name
        return result

    def _deserialise(self, data):
        super()._deserialise(data)
        self.ability = Ability.objects.get(name=data['ability'])

    def _generate_response_text(self, question):
        if self.useage_count == 0:
            if not self.ability:
                self.ability = question.abilities[0]
        else:
            if (
                    question.abilities
                    or question.heroes
                    or question.contains_any_string(self.COUNTER_WORDS)):
                raise InnapropriateContextError

        if question.contains_any_string(self.COOLDOWN_WORDS):
            return AbilityCooldownResponse.respond(self.ability, user_id=question.user_id)

        if question.contains_any_string(self.SPELL_IMMUNITY_WORDS):
            return AbilitySpellImmunityResponse.respond(self.ability, user_id=question.user_id)

        if question.contains_any_string(self.DAMAGE_TYPE_WORDS):
            return AbilityDamageTypeResponse.respond(self.ability, user_id=question.user_id)

        if self.useage_count == 0:
            if question.contains_any_string(self.ULTIMATE_WORDS):
                return AbilityUltimateResponse.respond(self.ability, user_id=question.user_id)
            if question.ability_hotkey:
                return AbilityHotkeyResponse.respond(self.ability, user_id=question.user_id)
            return AbilityDescriptionResponse.respond(self.ability, user_id=question.user_id)

        if question.contains_any_word(('what', )):
            return AbilityDescriptionResponse.respond(self.ability, user_id=question.user_id)

        raise InnapropriateContextError


class MultipleUltimateContext(Context):
    def _generate_response_text(self, question):
        return MultipleUltimateResponse.respond(hero=question.heroes[0], user_id=question.user_id)


class AbilityListContext(Context):
    _can_be_used_for_next_context = True
    _first_follow_up_question = "Any other hero?"
    _second_follow_up_question = "Any others?"
    _can_respond_to_yes_response = True
    _yes_response = "Which hero?"

    def _generate_response_text(self, question):
        if len(question.heroes) < 1:
            raise InnapropriateContextError
        if question.contains_any_string(self.COUNTER_WORDS):
            raise InnapropriateContextError
        return AbilityListResponse.respond(question.heroes[0], user_id=question.user_id)


class HeroAdvantageContext(Context):
    _can_be_used_for_next_context = True
    _first_follow_up_question = "Any specific role or hero you'd like to know about?"
    _second_follow_up_question = "Any others?"

    @unique
    class Direction(IntEnum):
        WHO_COUNTERS_HERO = 1
        WHO_DOES_HERO_COUNTER = 2

    def __init__(self, hero=None, direction=None):
        super().__init__()
        self.hero = hero
        self.direction = direction

    def serialise(self):
        result = super().serialise()
        result['hero'] = self.hero.name
        result['direction'] = self.direction
        return result

    def _deserialise(self, data):
        super()._deserialise(data)
        self.hero = Hero.objects.get(name=data['hero'])
        self.direction = data['direction']

    def _generate_response_text(self, question):
        if self.useage_count == 0:
            if len(question.heroes) == 1:
                self.hero = question.heroes[0]
                self.direction = self._calculate_direction(question)
            elif len(question.heroes) == 2:
                self.hero = question.heroes[1]
                self.direction = self.Direction.WHO_COUNTERS_HERO
            else:
                raise Exception("Question must have 1 or 2 heroes in it")
        if self.useage_count > 0:
            if len(question.heroes) == 0 and not question.role:
                raise InnapropriateContextError
            if len(question.heroes) == 1 and question.contains_any_string(
                    self.COUNTER_WORDS + self.ABILITY_WORDS + self.ULTIMATE_WORDS):
                raise InnapropriateContextError
            if len(question.heroes) > 1:
                raise InnapropriateContextError

        all_heroes = set(question.heroes + [self.hero])
        if len(all_heroes) == 2:
            other_hero = all_heroes.difference(set([self.hero])).pop()
            return TwoHeroAdvantageResponse.respond(
                hero=other_hero, enemy=self.hero, user_id=question.user_id)
        if len(all_heroes) == 1:
            if self.direction == self.Direction.WHO_COUNTERS_HERO:
                return SingleHeroCountersResponse.respond(
                    all_heroes.pop(), question.role, user_id=question.user_id)
            elif self.direction == self.Direction.WHO_DOES_HERO_COUNTER:
                return SingleHeroAdvantagesResponse.respond(
                    all_heroes.pop(), question.role, user_id=question.user_id)
            else:
                raise Exception("No direction specified")
        raise InnapropriateContextError

    @classmethod
    def _calculate_direction(cls, question):
        """Checks whether the question is asking, 'Who counters Axe?' or 'Who does Axe counter?'

        Also looks for the word 'bad' in the question and response accordingly, e.g.:
          'Who is bad against Axe?'
        """
        assert len(question.heroes) == 1
        if not question.contains_any_string(cls.COUNTER_WORDS):
            return cls.Direction.WHO_COUNTERS_HERO

        counter_position = question.position_of_first_string(cls.COUNTER_WORDS)
        bad_against = question.text[:counter_position].endswith('bad ')
        hero_position = question.position_of_first_string(
            (a.lower() for a in question.heroes[0].aliases))

        if counter_position <= hero_position:
            if not bad_against:
                return cls.Direction.WHO_COUNTERS_HERO
            else:
                return cls.Direction.WHO_DOES_HERO_COUNTER
        else:
            if not bad_against:
                return cls.Direction.WHO_DOES_HERO_COUNTER
            else:
                return cls.Direction.WHO_COUNTERS_HERO


class FeedbackContext(ContextWithBlankFollowUpQuestions):
    def _generate_response_text(self, question):
        if self.useage_count == 0:
            return "Great! What's your feedback?"
        if self.useage_count == 1:
            feedback_logger.info("%s: %s", question.user_id, question.text)
            return "Thanks, I'll look into it."
        raise InnapropriateContextError
