from rest_framework import serializers
from .models import Province, District, Municipality, Ward

class WardSerializer(serializers.ModelSerializer):
    municipality_name = serializers.ReadOnlyField(source='municipality.name')

    class Meta:
        model = Ward
        fields = ['id', 'ward_number', 'municipality', 'municipality_name']


class MunicipalitySerializer(serializers.ModelSerializer):
    district_name = serializers.ReadOnlyField(source='district.name')
    type_display = serializers.ReadOnlyField(source='get_type_display')
    wards = WardSerializer(many=True, read_only=True)

    class Meta:
        model = Municipality
        fields = ['id', 'name', 'type', 'type_display', 'district', 'district_name', 'wards']


class DistrictSerializer(serializers.ModelSerializer):
    province_name = serializers.ReadOnlyField(source='province.name')
    municipalities = MunicipalitySerializer(many=True, read_only=True)

    class Meta:
        model = District
        fields = ['id', 'name', 'province', 'province_name', 'municipalities']


class ProvinceSerializer(serializers.ModelSerializer):
    districts = DistrictSerializer(many=True, read_only=True)

    class Meta:
        model = Province
        fields = ['id', 'name', 'code', 'districts']
