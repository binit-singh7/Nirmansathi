from rest_framework import filters, permissions, viewsets

from .models import District, Municipality, Province, Ward
from .serializers import (
    DistrictSerializer,
    MunicipalitySerializer,
    ProvinceSerializer,
    WardSerializer,
)


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class ProvinceViewSet(viewsets.ModelViewSet):
    queryset = Province.objects.all()
    serializer_class = ProvinceSerializer
    permission_classes = [IsAdminOrReadOnly]


class DistrictViewSet(viewsets.ModelViewSet):
    queryset = District.objects.select_related('province').all()
    serializer_class = DistrictSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        queryset = super().get_queryset()
        province_id = self.request.query_params.get('province')
        if province_id:
            queryset = queryset.filter(province_id=province_id)
        return queryset


class MunicipalityViewSet(viewsets.ModelViewSet):
    queryset = Municipality.objects.select_related('district', 'district__province').all()
    serializer_class = MunicipalitySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'district__name', 'district__province__name', 'code']

    def get_queryset(self):
        queryset = super().get_queryset()
        include_all = self.request.query_params.get('include_all', '').lower() in ('true', '1', 'yes')
        if not include_all:
            queryset = queryset.exclude(type=Municipality.TypeChoices.RURAL_MUNICIPALITY)
        province_id = self.request.query_params.get('province') or self.request.query_params.get('province_id')
        if province_id:
            queryset = queryset.filter(district__province_id=province_id)
        district_id = self.request.query_params.get('district') or self.request.query_params.get('district_id')
        if district_id:
            queryset = queryset.filter(district_id=district_id)
        return queryset


class WardViewSet(viewsets.ModelViewSet):
    queryset = Ward.objects.select_related('municipality').all()
    serializer_class = WardSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['ward_number']

    def get_queryset(self):
        queryset = super().get_queryset()
        municipality_id = self.request.query_params.get('municipality')
        if municipality_id:
            queryset = queryset.filter(municipality_id=municipality_id)
        return queryset
