import logging
from django.http import HttpResponse, JsonResponse

from apps.metadata.models import User, DailyUse
from libs.google_actions import AppResponse, AppRequest, NoJsonException

from .response import ResponseGenerator, QuestionParser
from .exceptions import DoNotUnderstandQuestion


logger = logging.getLogger(__name__)
good_response_logger = logging.getLogger('good_response')


# # TODO
#
# # General
# Squish all the migrations
# Hero role accuracy
# More hero aliases
# Ability aliases
# Try it lots
# Do I really want the Hero model in hero advanteages?
#
# Questions
# Multiple ultimates (Dark Willow)
# Is X good/strong against Y?

# # V2
# Context and follow up questions
# Abilities with the same name, hex, blink
# Warn if an ability was not found this time when loading them (e.g. name change)
# Damage type
# Add the abilities of heroes summoned units
# Add abilities from talents or aghanims (be careful they don't override existing abilities, e.g. Brewmaster's Drunken Haze)  # noqa
# Talents
# Removable by types of dispel
# Linkens sphere interactions
# Ability duration
# Ability Range
# All details of spell
# Vision range of heroes
# Cast range


def index(request):
    try:
        google_request = AppRequest(request)
    except NoJsonException:
        return HttpResponse("Hello there, I'm a Google Assistant App.")

    User.log_user(google_request.user_id)
    if not google_request.text:
        return JsonResponse(AppResponse().ask("Hi, I'm Roshan. Ask me a question about Dota."))

    try:
        response = ResponseGenerator.respond(google_request.text)
    except DoNotUnderstandQuestion:
        DailyUse.log_use(success=False)
        return JsonResponse(AppResponse().ask(
            "Sorry, I don't understand. I heard you say: {}".format(google_request.text)))

    DailyUse.log_use(success=True)
    good_response_logger.info("%s Response: %s",
                              QuestionParser(google_request.text),
                              response)
    return JsonResponse(AppResponse().ask(response))
