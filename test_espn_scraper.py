#!/usr/bin/env python3
"""Tests for espn_pbp_scraper using mock ESPN API data."""

import json
import os
import sys
import unittest

# Add parent dir to path
sys.path.insert(0, os.path.dirname(__file__))

from espn_pbp_scraper import (
    extract_game_id,
    format_quarter,
    ordinal,
    parse_plays,
    format_down_distance,
    build_team_lookup,
)

# Mock ESPN API response matching the known JSON structure
MOCK_API_RESPONSE = {
    "header": {
        "competitions": [
            {
                "competitors": [
                    {
                        "homeAway": "home",
                        "team": {
                            "id": "57",
                            "abbreviation": "FLA",
                            "displayName": "Florida Gators",
                            "shortDisplayName": "Florida",
                            "location": "Florida",
                        },
                    },
                    {
                        "homeAway": "away",
                        "team": {
                            "id": "2",
                            "abbreviation": "MIA",
                            "displayName": "Miami Hurricanes",
                            "shortDisplayName": "Miami",
                            "location": "Miami",
                        },
                    },
                ]
            }
        ]
    },
    "drives": {
        "previous": [
            {
                "team": {
                    "id": "57",
                    "displayName": "Florida Gators",
                    "abbreviation": "FLA",
                },
                "plays": [
                    {
                        "text": "Carter Davis kickoff for 65 yds , Vernell Brown III return for 19 yds to the FLA 19",
                        "clock": {"displayValue": "15:00", "value": 900},
                        "period": {"number": 1},
                        "start": {
                            "down": 0,
                            "distance": 0,
                            "yardLine": 35,
                            "team": {"id": "57"},
                        },
                        "type": {"text": "Kickoff", "abbreviation": "K"},
                    },
                    {
                        "text": "Montrell Johnson Jr. rush for 5 yds to the FLA 24",
                        "clock": {"displayValue": "14:52", "value": 892},
                        "period": {"number": 1},
                        "start": {
                            "down": 1,
                            "distance": 10,
                            "yardLine": 19,
                            "team": {"id": "57"},
                        },
                        "type": {"text": "Rush", "abbreviation": "R"},
                    },
                    {
                        "text": "Graham Mertz pass complete to Ricky Pearsall for 12 yds to the FLA 36 for a 1ST down",
                        "clock": {"displayValue": "14:20", "value": 860},
                        "period": {"number": 1},
                        "start": {
                            "down": 2,
                            "distance": 5,
                            "yardLine": 24,
                            "team": {"id": "57"},
                        },
                        "type": {"text": "Pass", "abbreviation": "P"},
                    },
                ],
            },
            {
                "team": {
                    "id": "2",
                    "displayName": "Miami Hurricanes",
                    "abbreviation": "MIA",
                },
                "plays": [
                    {
                        "text": "Tyler Van Dyke pass incomplete to Xavier Restrepo",
                        "clock": {"displayValue": "10:30", "value": 630},
                        "period": {"number": 1},
                        "start": {
                            "down": 1,
                            "distance": 10,
                            "yardLine": 25,
                            "team": {"id": "2"},
                        },
                        "type": {"text": "Pass Incompletion", "abbreviation": "PI"},
                    },
                ],
            },
            # Drive in quarter 2
            {
                "team": {
                    "id": "57",
                    "displayName": "Florida Gators",
                    "abbreviation": "FLA",
                },
                "plays": [
                    {
                        "text": "Montrell Johnson Jr. rush for 3 yds to the MIA 47",
                        "clock": {"displayValue": "14:55", "value": 895},
                        "period": {"number": 2},
                        "start": {
                            "down": 1,
                            "distance": 10,
                            "yardLine": 50,
                            "team": {"id": "57"},
                        },
                        "type": {"text": "Rush", "abbreviation": "R"},
                    },
                ],
            },
            # OT drive
            {
                "team": {
                    "id": "2",
                    "displayName": "Miami Hurricanes",
                    "abbreviation": "MIA",
                },
                "plays": [
                    {
                        "text": "Tyler Van Dyke rush for 2 yds to the FLA 23",
                        "clock": {"displayValue": "0:00", "value": 0},
                        "period": {"number": 5},
                        "start": {
                            "down": 1,
                            "distance": 10,
                            "yardLine": 25,
                            "team": {"id": "57"},
                        },
                        "type": {"text": "Rush", "abbreviation": "R"},
                    },
                ],
            },
        ],
    },
}


class TestExtractGameId(unittest.TestCase):
    def test_plain_id(self):
        self.assertEqual(extract_game_id("401752709"), "401752709")

    def test_url_with_gameid_path(self):
        url = "https://www.espn.com/college-football/playbyplay/_/gameId/401752709"
        self.assertEqual(extract_game_id(url), "401752709")

    def test_url_with_gameid_param(self):
        url = "https://www.espn.com/college-football/playbyplay?gameId=401752709"
        self.assertEqual(extract_game_id(url), "401752709")

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            extract_game_id("not-a-game-id")


class TestFormatQuarter(unittest.TestCase):
    def test_regular_quarters(self):
        self.assertEqual(format_quarter(1), "1")
        self.assertEqual(format_quarter(2), "2")
        self.assertEqual(format_quarter(3), "3")
        self.assertEqual(format_quarter(4), "4")

    def test_overtime(self):
        self.assertEqual(format_quarter(5), "OT")
        self.assertEqual(format_quarter(6), "OT2")
        self.assertEqual(format_quarter(7), "OT3")

    def test_none(self):
        self.assertEqual(format_quarter(None), "")


class TestOrdinal(unittest.TestCase):
    def test_ordinals(self):
        self.assertEqual(ordinal(1), "1st")
        self.assertEqual(ordinal(2), "2nd")
        self.assertEqual(ordinal(3), "3rd")
        self.assertEqual(ordinal(4), "4th")
        self.assertEqual(ordinal(11), "11th")
        self.assertEqual(ordinal(12), "12th")
        self.assertEqual(ordinal(13), "13th")
        self.assertEqual(ordinal(21), "21st")


class TestParsePlays(unittest.TestCase):
    def setUp(self):
        self.plays = parse_plays(MOCK_API_RESPONSE)

    def test_total_plays(self):
        self.assertEqual(len(self.plays), 6)

    def test_first_play_possession(self):
        self.assertEqual(self.plays[0]["possession"], "Florida Gators")

    def test_first_play_quarter(self):
        self.assertEqual(self.plays[0]["quarter"], "1")

    def test_first_play_time(self):
        self.assertEqual(self.plays[0]["time"], "15:00")

    def test_first_play_text(self):
        self.assertIn("Carter Davis kickoff", self.plays[0]["play"])

    def test_second_play_down_dist(self):
        # 1st & 10 at FLA 19
        dd = self.plays[1]["down_dist"]
        self.assertIn("1st", dd)
        self.assertIn("10", dd)
        self.assertIn("FLA", dd)
        self.assertIn("19", dd)

    def test_third_play_down_dist(self):
        # 2nd & 5 at FLA 24
        dd = self.plays[2]["down_dist"]
        self.assertIn("2nd", dd)
        self.assertIn("5", dd)
        self.assertIn("FLA", dd)
        self.assertIn("24", dd)

    def test_miami_possession(self):
        # 4th play is Miami's
        self.assertEqual(self.plays[3]["possession"], "Miami Hurricanes")

    def test_quarter_2(self):
        self.assertEqual(self.plays[4]["quarter"], "2")

    def test_overtime(self):
        self.assertEqual(self.plays[5]["quarter"], "OT")
        self.assertEqual(self.plays[5]["possession"], "Miami Hurricanes")

    def test_overtime_down_dist_cross_team(self):
        # OT play: 1st & 10 at FLA 25 (Miami possession, ball at Florida's yard)
        dd = self.plays[5]["down_dist"]
        self.assertIn("1st", dd)
        self.assertIn("10", dd)
        self.assertIn("FLA", dd)
        self.assertIn("25", dd)


class TestBuildTeamLookup(unittest.TestCase):
    def test_lookup_has_both_teams(self):
        lookup = build_team_lookup(MOCK_API_RESPONSE)
        self.assertIn("57", lookup)
        self.assertIn("2", lookup)
        self.assertEqual(lookup["57"]["abbreviation"], "FLA")
        self.assertEqual(lookup["2"]["abbreviation"], "MIA")


class TestFormatDownDistance(unittest.TestCase):
    def test_normal_play(self):
        team_lookup = {"57": {"abbreviation": "FLA"}}
        play = {
            "start": {
                "down": 1,
                "distance": 10,
                "yardLine": 19,
                "team": {"id": "57"},
            }
        }
        result = format_down_distance(play, team_lookup)
        self.assertEqual(result, "1st & 10 at FLA 19")

    def test_kickoff_no_down(self):
        play = {
            "start": {
                "down": 0,
                "distance": 0,
                "yardLine": 35,
                "team": {"id": "57", "abbreviation": "FLA"},
            }
        }
        result = format_down_distance(play, {})
        self.assertIn("FLA", result)
        self.assertIn("35", result)

    def test_empty_start(self):
        result = format_down_distance({}, {})
        self.assertEqual(result, "")


class TestEdgeCases(unittest.TestCase):
    def test_empty_drives(self):
        data = {"drives": {}, "header": {"competitions": []}}
        plays = parse_plays(data)
        self.assertEqual(len(plays), 0)

    def test_no_drives_key(self):
        data = {"header": {"competitions": []}}
        plays = parse_plays(data)
        self.assertEqual(len(plays), 0)

    def test_current_drive_included(self):
        data = {
            "header": {"competitions": []},
            "drives": {
                "previous": [],
                "current": {
                    "team": {"displayName": "Test Team"},
                    "plays": [
                        {
                            "text": "Test play",
                            "clock": {"displayValue": "5:00"},
                            "period": {"number": 3},
                            "start": {},
                        }
                    ],
                },
            },
        }
        plays = parse_plays(data)
        self.assertEqual(len(plays), 1)
        self.assertEqual(plays[0]["possession"], "Test Team")
        self.assertEqual(plays[0]["quarter"], "3")

    def test_team_id_only_resolved_via_lookup(self):
        """When drive team only has an ID, resolve via header lookup."""
        data = {
            "header": {
                "competitions": [
                    {
                        "competitors": [
                            {
                                "team": {
                                    "id": "99",
                                    "abbreviation": "TST",
                                    "displayName": "Test University",
                                }
                            }
                        ]
                    }
                ]
            },
            "drives": {
                "previous": [
                    {
                        "team": {"id": "99"},
                        "plays": [
                            {
                                "text": "A play",
                                "clock": {"displayValue": "12:00"},
                                "period": {"number": 1},
                                "start": {
                                    "down": 3,
                                    "distance": 7,
                                    "yardLine": 40,
                                    "team": {"id": "99"},
                                },
                            }
                        ],
                    }
                ]
            },
        }
        plays = parse_plays(data)
        self.assertEqual(plays[0]["possession"], "Test University")
        self.assertIn("3rd", plays[0]["down_dist"])
        self.assertIn("7", plays[0]["down_dist"])
        self.assertIn("TST", plays[0]["down_dist"])


if __name__ == "__main__":
    unittest.main()
