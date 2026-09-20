from rest_framework.routers import DefaultRouter
from .views import PermitApplicationViewSet, ApplicationDocumentViewSet, ConstructionPhaseViewSet

router = DefaultRouter()
router.register(r'applications', PermitApplicationViewSet, basename='permit_application')
router.register(r'documents', ApplicationDocumentViewSet, basename='permit_document')
router.register(r'phases', ConstructionPhaseViewSet, basename='construction_phase')

urlpatterns = router.urls

