from rest_framework import viewsets, permissions
from .models import Province, District, Municipality, Ward
from .serializers import (
    ProvinceSerializer,
    DistrictSerializer,
    MunicipalitySerializer,
    WardSerializer
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
    filterset_fields = ['province']

class MunicipalityViewSet(viewsets.ModelViewSet):
    queryset = Municipality.objects.select_related('district', 'district__province').all()
    serializer_class = MunicipalitySerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['district', 'district__province']

class WardViewSet(viewsets.ModelViewSet):
    queryset = Ward.objects.select_related('municipality').all()
    serializer_class = WardSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['municipality']
