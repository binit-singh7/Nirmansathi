from django.contrib import admin
from .models import PaymentTransaction

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_code', 'order', 'user', 'amount', 'status', 'created_at')
    list_filter = ('status', 'payment_method')
    search_fields = ('transaction_code', 'order__order_reference', 'user__username')
    readonly_fields = ('transaction_code', 'order', 'user', 'amount', 'status', 'gateway_response', 'created_at')
