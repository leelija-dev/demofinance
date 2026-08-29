# Default empty tests module for agent_location app.
from django.test import SimpleTestCase


class SmokeTests(SimpleTestCase):
    def test_services_import(self):
        from agent_location.services import is_valid_coordinate, parse_coordinate
        self.assertTrue(is_valid_coordinate(parse_coordinate('22.57'), parse_coordinate('88.36')))
        self.assertFalse(is_valid_coordinate(parse_coordinate('0'), parse_coordinate('0')))
