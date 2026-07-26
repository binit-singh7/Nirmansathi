from rest_framework import serializers
from .models import PaymentTransaction

class PaymentTransactionSerializer(serializers.ModelSerializer):
    order_reference = serializers.ReadOnlyField(source='order.order_reference')
    user_name = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'transaction_code', 'order', 'order_reference',
            'user', 'user_name', 'payment_method', 'amount',
            'status', 'remarks', 'gateway_response', 'created_at'
        ]
        read_only_fields = ['id', 'transaction_code', 'user', 'created_at']


class SimulatePaymentSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(required=True)
    simulate_failure = serializers.BooleanField(default=False, required=False, help_text="Set to true to test payment rejection flow")
    remarks = serializers.CharField(required=False, allow_blank=True, default="Simulated eSewa Payment")
