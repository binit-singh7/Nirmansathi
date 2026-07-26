from django.urls import path
from .views import SimulateEsewaPaymentView, PaymentTransactionListView

urlpatterns = [
    path('esewa/simulate/', SimulateEsewaPaymentView.as_view(), name='simulate_esewa_payment'),
    path('transactions/', PaymentTransactionListView.as_view(), name='payment_transaction_list'),
]
