from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

# Customize Django Admin Branding
admin.site.site_header = "DIGITAL CONSTRUCTION PLATFORM"
admin.site.site_title = "NirmanSathi Admin"
admin.site.index_title = "NirmanSathi System Administration"

urlpatterns = [
    # Home Page
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    
    # Language switcher (POST target for the set_language form)
    path('i18n/', include('django.conf.urls.i18n')),

    # Direct Web Page Routes (HTML Templates)
    path('login/', TemplateView.as_view(template_name='accounts/login.html'), name='login'),
    path('register/', TemplateView.as_view(template_name='accounts/register.html'), name='register'),
    path('configuration/', TemplateView.as_view(template_name='configuration.html'), name='configuration'),
    path('accounts/audit-logs/', TemplateView.as_view(template_name='accounts/audit_logs.html'), name='audit_logs'),

    # Role Dashboards
    path('dashboard/citizen/', TemplateView.as_view(template_name='dashboard/citizen_dashboard.html'), name='citizen_dashboard'),
    path('dashboard/officer/', TemplateView.as_view(template_name='dashboard/officer_dashboard.html'), name='officer_dashboard'),
    path('dashboard/supplier/', TemplateView.as_view(template_name='dashboard/supplier_dashboard.html'), name='supplier_dashboard'),
    path('dashboard/admin/', TemplateView.as_view(template_name='dashboard/admin_dashboard.html'), name='admin_dashboard'),

    # Permits Pages
    path('permits/apply/', TemplateView.as_view(template_name='permits/application_create.html'), name='permit_create'),
    path('permits/my-applications/', TemplateView.as_view(template_name='permits/application_list.html'), name='permit_list'),
    path('permits/<int:pk>/', TemplateView.as_view(template_name='permits/application_detail.html'), name='permit_detail'),
    path('permits/officer/review/<int:pk>/', TemplateView.as_view(template_name='permits/officer_review.html'), name='officer_review'),

    # Marketplace Pages
    path('marketplace/', TemplateView.as_view(template_name='marketplace/product_list.html'), name='product_list'),
    path('marketplace/products/<int:pk>/', TemplateView.as_view(template_name='marketplace/product_detail.html'), name='product_detail'),
    path('marketplace/cart/', TemplateView.as_view(template_name='marketplace/cart.html'), name='cart'),
    path('marketplace/checkout/', TemplateView.as_view(template_name='marketplace/checkout.html'), name='checkout'),
    path('marketplace/payment-simulation/', TemplateView.as_view(template_name='marketplace/payment_simulation.html'), name='payment_simulation'),
    path('marketplace/orders/', TemplateView.as_view(template_name='marketplace/order_list.html'), name='order_list'),
    path('marketplace/orders/<int:pk>/', TemplateView.as_view(template_name='marketplace/order_detail.html'), name='order_detail'),
    path('marketplace/supplier/products/', TemplateView.as_view(template_name='marketplace/product_manage.html'), name='supplier_product_manage'),
    path('marketplace/products/manage/', TemplateView.as_view(template_name='marketplace/product_manage.html'), name='product_manage'),
    path('marketplace/supplier/orders/', TemplateView.as_view(template_name='marketplace/supplier_order_list.html'), name='supplier_order_list'),

    # Django Admin Panel
    path('admin/', admin.site.urls),

    # Backend REST API endpoints (consumed by base.js & frontend)
    path('api/v1/accounts/', include('accounts.urls')),
    path('api/v1/locations/', include('locations.urls')),
    path('api/v1/permits/', include('permits.urls')),
    path('api/v1/marketplace/', include('marketplace.urls')),
    path('api/v1/payments/', include('payments.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
