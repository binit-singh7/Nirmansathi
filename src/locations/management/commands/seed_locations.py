import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from locations.models import District, Municipality, Province, Ward


class Command(BaseCommand):
    help = 'Seed Nepal administrative locations from a local JSON or GeoJSON dataset.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            dest='data_file',
            default=None,
            help='Path to a JSON/GeoJSON file containing provinces, districts, municipalities, and wards.',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            dest='clear',
            default=False,
            help='Clear all existing location data before seeding.',
        )

    def handle(self, *args, **options):
        if options.get('clear'):
            self.stdout.write(self.style.WARNING('Clearing all existing location data...'))
            try:
                Province.objects.all().delete()
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Could not clear all existing location entries due to existing application references: {exc}"))

        # Safely remove any non-protected Gaunpalika entries
        for gapa in Municipality.objects.filter(type=Municipality.TypeChoices.RURAL_MUNICIPALITY):
            try:
                gapa.delete()
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Skipping deletion of referenced Gaunpalika '{gapa.name}': {exc}"))

        data_path = self._resolve_data_path(options.get('data_file'))

        if not data_path.exists():
            raise CommandError(f"Locations JSON file not found: {data_path}")

        try:
            payload = json.loads(data_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Malformed JSON in {data_path}: {exc}") from exc
        except OSError as exc:
            raise CommandError(f"Unable to read locations file: {exc}") from exc

        if self._looks_like_geojson(payload):
            self._seed_geojson(payload, data_path)
            return

        if isinstance(payload, dict):
            provinces_data = payload.get('provinces') or payload.get('data')
        else:
            provinces_data = payload

        if not isinstance(provinces_data, list):
            raise CommandError("Expected JSON root to be a list of provinces or a dictionary with a 'provinces' list.")

        with transaction.atomic():
            self.stdout.write(self.style.NOTICE('Seeding Nepal locations...'))
            for index, province_data in enumerate(provinces_data, start=1):
                province_name = province_data.get('name')
                if not province_name:
                    self.stderr.write(self.style.WARNING('Skipping province entry with missing name.'))
                    continue

                province_code = self._resolve_province_code(province_data, index)
                province = Province.objects.filter(Q(name=province_name) | Q(code=province_code)).first()
                if province:
                    created = False
                    if province.name != province_name or province.code != province_code:
                        province.name = province_name
                        province.code = province_code
                        province.save(update_fields=['name', 'code'])
                else:
                    province = Province.objects.create(name=province_name, code=province_code)
                    created = True

                self.stdout.write(self.style.SUCCESS(
                    f"Province: {province.name} ({'created' if created else 'exists'})"
                ))

                for district_data in province_data.get('districts', []):
                    district_name = district_data.get('name')
                    if not district_name:
                        self.stderr.write(self.style.WARNING(f"Skipping district entry under {province.name} with missing name."))
                        continue

                    district, created = District.objects.get_or_create(
                        province=province,
                        name=district_name,
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f"  District: {district.name} ({'created' if created else 'exists'})"
                    ))

                    for municipality_data in district_data.get('municipalities', []):
                        municipality_name = municipality_data.get('name')
                        municipality_type = municipality_data.get('type', Municipality.TypeChoices.MUNICIPALITY)

                        if not municipality_name:
                            self.stderr.write(self.style.WARNING(
                                f"Skipping municipality entry under {district.name} with missing name."
                            ))
                            continue

                        # Filter out Gaunpalika (Rural Municipality)
                        if municipality_type == Municipality.TypeChoices.RURAL_MUNICIPALITY or 'gaunpalika' in municipality_name.lower() or 'rural municipality' in municipality_name.lower():
                            self.stdout.write(self.style.NOTICE(
                                f"    Skipping Gaunpalika (Rural Municipality): {municipality_name}"
                            ))
                            continue

                        if municipality_type not in dict(Municipality.TypeChoices.choices):
                            self.stderr.write(self.style.WARNING(
                                f"Invalid municipality type '{municipality_type}' for {municipality_name}; defaulting to MUNICIPALITY."
                            ))
                            municipality_type = Municipality.TypeChoices.MUNICIPALITY

                        municipality, created = Municipality.objects.get_or_create(
                            district=district,
                            name=municipality_name,
                            defaults={'type': municipality_type},
                        )

                        if not created and municipality.type != municipality_type:
                            municipality.type = municipality_type
                            municipality.save(update_fields=['type'])

                        self.stdout.write(self.style.SUCCESS(
                            f"    Municipality: {municipality.name} ({municipality.get_type_display()}) "
                            f"({'created' if created else 'exists'})"
                        ))

                        wards = municipality_data.get('wards', [])
                        if not wards and 'total_wards' in municipality_data:
                            wards = list(range(1, municipality_data['total_wards'] + 1))
                        elif not wards:
                            wards = self._get_default_ward_range(municipality_name, municipality_type)

                        for ward_number in wards:
                            if not isinstance(ward_number, int):
                                self.stderr.write(self.style.WARNING(
                                    f"Skipping invalid ward number '{ward_number}' in {municipality.name}."
                                ))
                                continue

                            ward, created = Ward.objects.get_or_create(
                                municipality=municipality,
                                ward_number=ward_number,
                            )
                            self.stdout.write(self.style.SUCCESS(
                                f"      Ward: {ward.ward_number} ({'created' if created else 'exists'})"
                            ))

            self.stdout.write(self.style.SUCCESS('Nepal location data seeded successfully.'))

    def _seed_geojson(self, payload, data_path):
        features = payload.get('features', []) if isinstance(payload, dict) else payload
        if not isinstance(features, list) or not features:
            raise CommandError(f"No GeoJSON features found in {data_path}")

        self.stdout.write(self.style.NOTICE(f"Importing {len(features)} GeoJSON features from {data_path}..."))

        created_counts = {'province': 0, 'district': 0, 'municipality': 0, 'ward': 0}

        with transaction.atomic():
            for index, feature in enumerate(features, start=1):
                properties = feature.get('properties', {}) if isinstance(feature, dict) else {}
                if not isinstance(properties, dict):
                    continue

                province_code = self._extract_province_code(properties)
                province_name = self._normalize_province_name(properties)
                district_name = self._extract_value(properties, ['DISTRICT', 'district', 'district_name', 'districtName'])
                municipality_name = self._extract_value(properties, ['GaPa_NaPa', 'municipality', 'municipality_name', 'municipalityName', 'name'])
                municipality_type = self._extract_municipality_type(properties)
                ward_number = self._extract_ward_number(properties)

                if not province_name or not district_name or not municipality_name:
                    self.stderr.write(self.style.WARNING(f"Skipping feature {index}: missing required values."))
                    continue

                # Filter out Gaunpalika (Rural Municipality) and reserves
                raw_type = properties.get('Type_GN', '')
                if municipality_type == Municipality.TypeChoices.RURAL_MUNICIPALITY or 'gaunpalika' in municipality_name.lower() or 'rural municipality' in municipality_name.lower() or raw_type in ['National Park', 'Wildlife Reserve', 'Hunting Reserve', 'Development Area', 'Watershed and Wildlife Reserve']:
                    continue

                if self._looks_like_placeholder(district_name, 'district') or self._looks_like_placeholder(municipality_name, 'municipality'):
                    self.stderr.write(self.style.WARNING(f"Skipping feature {index}: placeholder name '{district_name}' / '{municipality_name}'."))
                    continue

                district_name = district_name.strip().title()
                municipality_name = municipality_name.strip().title()

                if municipality_type == Municipality.TypeChoices.METROPOLITAN and not municipality_name.endswith('Metropolitan City'):
                    municipality_name = f"{municipality_name} Metropolitan City"
                elif municipality_type == Municipality.TypeChoices.SUB_METROPOLITAN and not municipality_name.endswith('Sub-Metropolitan City'):
                    municipality_name = f"{municipality_name} Sub-Metropolitan City"
                elif municipality_type == Municipality.TypeChoices.MUNICIPALITY and not municipality_name.endswith('Municipality'):
                    municipality_name = f"{municipality_name} Municipality"

                province = Province.objects.filter(Q(name=province_name) | Q(code=province_code)).first()
                if province:
                    province_created = False
                    if province.name != province_name or province.code != province_code:
                        province.name = province_name
                        province.code = province_code
                        province.save(update_fields=['name', 'code'])
                else:
                    province = Province.objects.create(name=province_name, code=province_code)
                    province_created = True

                district, district_created = District.objects.get_or_create(
                    province=province,
                    name=district_name,
                )
                if district_created:
                    created_counts['district'] += 1

                municipality, municipality_created = Municipality.objects.get_or_create(
                    district=district,
                    name=municipality_name,
                    defaults={'type': municipality_type},
                )
                if municipality_created:
                    created_counts['municipality'] += 1
                elif municipality.type != municipality_type:
                    municipality.type = municipality_type
                    municipality.save(update_fields=['type'])

                ward_numbers = [ward_number] if ward_number is not None else self._get_default_ward_range(municipality_name, municipality_type)
                for ward_number_to_create in ward_numbers:
                    ward, ward_created = Ward.objects.get_or_create(
                        municipality=municipality,
                        ward_number=ward_number_to_create,
                    )
                    if ward_created:
                        created_counts['ward'] += 1

        self.stdout.write(self.style.SUCCESS(
            'GeoJSON import complete. ' 
            f"Created: provinces={created_counts['province']}, districts={created_counts['district']}, "
            f"municipalities={created_counts['municipality']}, wards={created_counts['ward']}."
        ))

    def _looks_like_geojson(self, payload):
        return isinstance(payload, dict) and isinstance(payload.get('features'), list)

    def _resolve_data_path(self, data_file):
        if data_file:
            path = Path(data_file).expanduser()
            if not path.is_absolute():
                path = Path.cwd() / path
            return path
        geojson_path = Path(__file__).resolve().parents[2] / 'data' / 'nepal.geojson'
        if geojson_path.exists():
            return geojson_path
        return Path(__file__).resolve().parents[2] / 'data' / 'nepal_locations.json'

    def _resolve_province_code(self, province_data, index):
        raw_code = province_data.get('code') or province_data.get('province_code') or province_data.get('province_number')
        if isinstance(raw_code, int):
            return raw_code
        if isinstance(raw_code, str) and raw_code.isdigit():
            return int(raw_code)
        return index

    def _extract_province_code(self, properties):
        for key in ['STATE_CODE', 'province_code', 'provinceCode', 'code', 'Province']:
            value = properties.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        return 1

    def _normalize_province_name(self, properties):
        province_value = self._extract_value(properties, ['Province', 'province', 'province_name', 'provinceName'])
        if province_value is None:
            return 'Province 1'
        if isinstance(province_value, str) and province_value.isdigit():
            return f"Province {province_value}"
        return f"Province {province_value}"

    def _extract_value(self, properties, keys):
        for key in keys:
            if key in properties and properties[key] not in (None, ''):
                value = properties[key]
                if isinstance(value, str):
                    value = value.strip()
                return value
        return None

    def _extract_ward_number(self, properties):
        raw = self._extract_value(properties, ['WARD', 'ward', 'ward_number', 'wardNumber', 'ward_no', 'wardNo'])
        if raw is None:
            return None
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str):
            match = re.search(r'\d+', raw)
            if match:
                return int(match.group(0))
        return None

    KNOWN_WARD_COUNTS = {
        'kathmandu': 32,
        'lalitpur': 29,
        'pokhara': 33,
        'biratnagar': 19,
        'birgunj': 32,
        'bharatpur': 29,
        'budhanilkantha': 13,
        'dharan': 20,
        'itahari': 20,
        'janakpur': 25,
        'janakpurdham': 25,
        'butwal': 19,
        'tulsipur': 19,
        'ghorahi': 19,
        'dhangadhi': 19,
        'hetauda': 19,
        'jitpur simara': 24,
        'kalaiya': 27,
        'nepalgunj': 23,
        'bhaktapur': 10,
        'madhyapur thimi': 9,
        'suryabinayak': 10,
        'changunarayan': 9,
        'tokha': 11,
        'kageshwari manohara': 9,
        'gokarneshwar': 9,
        'tarakeshwar': 11,
        'nagarjun': 10,
        'chandragiri': 15,
        'kirtipur': 10,
        'dakshinkali': 9,
        'shankharapur': 9,
        'mahalaxmi': 10,
        'godawari': 14,
        'birtamod': 10,
        'damak': 10,
        'mechinagar': 15,
        'ratnanagar': 16,
        'siddharthanagar': 13,
        'tilottama': 17,
        'birendranagar': 16,
        'tikapur': 9,
    }

    def _get_default_ward_range(self, municipality_name, municipality_type):
        clean_name = municipality_name.lower().replace('municipality', '').replace('metropolitan city', '').replace('sub-metropolitan city', '').replace('nagarpalika', '').strip()
        if clean_name in self.KNOWN_WARD_COUNTS:
            return list(range(1, self.KNOWN_WARD_COUNTS[clean_name] + 1))

        if municipality_type == Municipality.TypeChoices.METROPOLITAN:
            return list(range(1, 26))
        elif municipality_type == Municipality.TypeChoices.SUB_METROPOLITAN:
            return list(range(1, 21))
        else:
            return list(range(1, 13))

    def _looks_like_placeholder(self, value, kind):
        if not isinstance(value, str):
            return False

        normalized = re.sub(r'\s+', ' ', value.strip()).lower()
        if kind == 'district':
            return bool(re.match(r'^district\s+[a-z]$', normalized))
        if kind == 'municipality':
            return bool(re.match(r'^(?:a|b|c|d|e|f|g|h|i|j|k|l|m|n|o|p|q|r|s|t|u|v|w|x|y|z)\s+(?:municipality|rural municipality|metropolitan city|sub-metropolitan city)$', normalized))
        return False

    def _extract_municipality_type(self, properties):
        raw_type = self._extract_value(properties, ['Type_GN', 'type', 'municipality_type', 'municipalityType', 'class'])
        if not raw_type:
            return Municipality.TypeChoices.MUNICIPALITY

        normalized = str(raw_type).strip().lower().replace(' ', '_')
        mapping = {
            'metropolitan': Municipality.TypeChoices.METROPOLITAN,
            'metropolitan_city': Municipality.TypeChoices.METROPOLITAN,
            'sub_metropolitan': Municipality.TypeChoices.SUB_METROPOLITAN,
            'sub_metropolitan_city': Municipality.TypeChoices.SUB_METROPOLITAN,
            'municipality': Municipality.TypeChoices.MUNICIPALITY,
            'nagarpalika': Municipality.TypeChoices.MUNICIPALITY,
            'gaunpalika': Municipality.TypeChoices.RURAL_MUNICIPALITY,
            'rural_municipality': Municipality.TypeChoices.RURAL_MUNICIPALITY,
            'mahanagarpalika': Municipality.TypeChoices.METROPOLITAN,
        }
        return mapping.get(normalized, Municipality.TypeChoices.MUNICIPALITY)
