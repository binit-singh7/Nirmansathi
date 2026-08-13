import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from locations.models import District, Municipality, Province, Ward


class SeedLocationsCommandTests(TestCase):
    def test_seed_geojson_creates_province_district_municipality_and_wards(self):
        geojson_payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "STATE_CODE": 1,
                        "DISTRICT": "KATHMANDU",
                        "GaPa_NaPa": "Budhanilkantha",
                        "Type_GN": "Nagarpalika",
                        "Province": "1",
                    },
                    "geometry": {"type": "Polygon", "coordinates": []},
                }
            ],
        }

        with tempfile.NamedTemporaryFile("w", suffix=".geojson", delete=False, encoding="utf-8") as handle:
            json.dump(geojson_payload, handle)
            temp_path = handle.name

        try:
            call_command("seed_locations", data_file=temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

        province = Province.objects.get(code=1)
        self.assertEqual(province.name, "Province 1")

        district = District.objects.get(province=province, name="KATHMANDU")
        municipality = Municipality.objects.get(district=district, name="Budhanilkantha")
        self.assertEqual(municipality.type, Municipality.TypeChoices.MUNICIPALITY)

        wards = list(Ward.objects.filter(municipality=municipality).values_list('ward_number', flat=True))
        self.assertEqual(wards, list(range(1, 14)))

    def test_seed_geojson_skips_gaunpalika_rural_municipalities(self):
        geojson_payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "STATE_CODE": 1,
                        "DISTRICT": "KATHMANDU",
                        "GaPa_NaPa": "Sample Gaunpalika",
                        "Type_GN": "Gaunpalika",
                        "Province": "1",
                    },
                    "geometry": {"type": "Polygon", "coordinates": []},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "STATE_CODE": 1,
                        "DISTRICT": "KATHMANDU",
                        "GaPa_NaPa": "Budhanilkantha Nagarpalika",
                        "Type_GN": "Nagarpalika",
                        "Province": "1",
                    },
                    "geometry": {"type": "Polygon", "coordinates": []},
                },
            ],
        }

        with tempfile.NamedTemporaryFile("w", suffix=".geojson", delete=False, encoding="utf-8") as handle:
            json.dump(geojson_payload, handle)
            temp_path = handle.name

        try:
            call_command("seed_locations", data_file=temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

        self.assertFalse(Municipality.objects.filter(name="Sample Gaunpalika").exists())
        self.assertTrue(Municipality.objects.filter(name="Budhanilkantha Nagarpalika").exists())


class LocationHierarchyApiTests(TestCase):
    def test_location_endpoints_filter_by_selected_parent(self):
        province_1 = Province.objects.create(name="Province 1", code=1)
        province_2 = Province.objects.create(name="Province 2", code=2)

        district_1 = District.objects.create(province=province_1, name="Kathmandu")
        district_2 = District.objects.create(province=province_2, name="Pokhara")

        municipality_1 = Municipality.objects.create(district=district_1, name="Budhanilkantha")
        municipality_2 = Municipality.objects.create(district=district_2, name="Lekhnath")

        Ward.objects.create(municipality=municipality_1, ward_number=1)
        Ward.objects.create(municipality=municipality_2, ward_number=2)

        response = self.client.get('/api/v1/locations/districts/', {'province': province_1.id})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['name'], 'Kathmandu')

        response = self.client.get('/api/v1/locations/municipalities/', {'district': district_1.id})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['name'], 'Budhanilkantha')

        response = self.client.get('/api/v1/locations/wards/', {'municipality': municipality_1.id})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['ward_number'], 1)
