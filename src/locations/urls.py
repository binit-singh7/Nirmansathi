from rest_framework.routers import DefaultRouter
from .views import ProvinceViewSet, DistrictViewSet, MunicipalityViewSet, WardViewSet

router = DefaultRouter()
router.register(r'provinces', ProvinceViewSet, basename='province')
router.register(r'districts', DistrictViewSet, basename='district')
router.register(r'municipalities', MunicipalityViewSet, basename='municipality')
router.register(r'wards', WardViewSet, basename='ward')

urlpatterns = router.urls
