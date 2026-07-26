from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
import views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API endpoints v1
    path('api/v1/accounts/', include('accounts.urls')),
    path('api/v1/locations/', include('locations.urls')),
    path('api/v1/permits/', include('permits.urls')),
    path('api/v1/marketplace/', include('marketplace.urls')),
    path('api/v1/payments/', include('payments.urls')),

    # Frontend View Routes
    path('', include([
        path('', views.HomeView.as_view(), name='home'),
        path('login/', views.LoginView.as_view(), name='login'),
        path('register/', views.RegisterView.as_view(), name='register'),
        path('dashboard/citizen/', views.CitizenDashboardView.as_view(), name='citizen_dashboard'),
        path('permits/apply/', views.PermitCreateView.as_view(), name='permit_create'),
        path('permits/my-applications/', views.PermitListView.as_view(), name='permit_list'),
        path('permits/<int:pk>/', views.PermitDetailView.as_view(), name='permit_detail'),
        path('marketplace/', views.ProductListView.as_view(), name='product_list'),
        path('marketplace/products/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
        path('marketplace/cart/', views.CartView.as_view(), name='cart'),
        path('marketplace/checkout/', views.CheckoutView.as_view(), name='checkout'),
        path('marketplace/payment-simulation/', views.PaymentSimulationView.as_view(), name='payment_simulation'),
        path('marketplace/orders/', views.OrderListView.as_view(), name='order_list'),
        path('marketplace/orders/<int:pk>/', views.OrderDetailView.as_view(), name='order_detail'),
        path('dashboard/officer/', views.OfficerDashboardView.as_view(), name='officer_dashboard'),
        path('permits/officer/review/<int:pk>/', views.OfficerReviewView.as_view(), name='officer_review'),
        path('dashboard/supplier/', views.SupplierDashboardView.as_view(), name='supplier_dashboard'),
        path('marketplace/supplier/products/', views.SupplierProductManageView.as_view(), name='supplier_product_manage'),
        path('marketplace/supplier/orders/', views.SupplierOrderListView.as_view(), name='supplier_order_list'),
        path('dashboard/admin/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
        path('admin-portal/users/', views.AdminUserListView.as_view(), name='admin_user_list'),
        path('admin-portal/locations/', views.AdminLocationView.as_view(), name='admin_location_list'),
    ])),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
