from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API endpoints v1
    path('api/v1/accounts/', include('accounts.urls')),
    path('api/v1/locations/', include('locations.urls')),
    path('api/v1/permits/', include('permits.urls')),
    path('api/v1/marketplace/', include('marketplace.urls')),
    path('api/v1/payments/', include('payments.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
