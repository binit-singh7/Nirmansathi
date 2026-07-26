from rest_framework.routers import DefaultRouter
from .views import PermitApplicationViewSet, ApplicationDocumentViewSet

router = DefaultRouter()
router.register(r'applications', PermitApplicationViewSet, basename='permit_application')
router.register(r'documents', ApplicationDocumentViewSet, basename='permit_document')

urlpatterns = router.urls
