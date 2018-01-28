import py
import pytest

from django.test import TestCase

from apps.utils.request_handler import MockRequestHandler
from apps.hero_advantages.factories import HeroFactory

from .models import Ability
from .web_scraper import WebScraper

mock_request_handler = MockRequestHandler(
    url_map={
        "https://dota2.gamepedia.com/Disruptor": "Disruptor - Dota 2 Wiki.html",
        "https://dota2.gamepedia.com/Phantom_Lancer": "Phantom Lancer - Dota 2 Wiki.html",
        "https://dota2.gamepedia.com/Dark_Willow": "Dark Willow - Dota 2 Wiki.html",
    },
    files_path=py.path.local().join("apps", "hero_abilities", "test_data"),
)


@pytest.mark.django_db
class TestWebScraper(TestCase):
    @property
    def scraper(self):
        return WebScraper(request_handler=mock_request_handler)

    def test_loads_all_abilities(self):
        disruptor = HeroFactory(name='Disruptor')
        self.scraper.load_hero_abilities(disruptor)

        self.assertEqual(Ability.objects.count(), 4)
        self.assertTrue(all(
            ability.hero == disruptor
            for ability in Ability.objects.all()
        ))

    def test_loads_kinetic_field(self):
        self.scraper.load_hero_abilities(HeroFactory(name='Disruptor'))

        kinetic_field = Ability.objects.get(name='Kinetic Field')
        self.assertEqual(kinetic_field.cooldown, '13/12/11/10')
        self.assertEqual(kinetic_field.hotkey, 'E')
        self.assertFalse(kinetic_field.is_ultimate)

    def test_loads_ultimate(self):
        self.scraper.load_hero_abilities(HeroFactory(name='Disruptor'))
        self.assertTrue(Ability.objects.get(name='Static Storm').is_ultimate)

    def test_abilities_with_no_cooldown(self):
        self.scraper.load_hero_abilities(HeroFactory(name='Phantom Lancer'))
        assert Ability.objects.get(name='Juxtapose').cooldown == ''

    def test_talent_abilities(self):
        self.scraper.load_hero_abilities(HeroFactory(name='Phantom Lancer'))
        assert Ability.objects.get(name='Critical Strike').is_from_talent
        assert Ability.objects.filter(is_from_talent=False).count() == 4

    def test_abilities_with_long_headers(self):
        self.scraper.load_hero_abilities(HeroFactory(name='Dark Willow'))
        for ability in Ability.objects.all():
            assert len(ability.hotkey) == 1
