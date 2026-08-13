import uuid
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction

from marketplace.models import Order
from .models import PaymentTransaction
from .serializers import PaymentTransactionSerializer, SimulatePaymentSerializer
from accounts.utils import log_audit
from accounts.models import AuditLog

class SimulateEsewaPaymentView(APIView):
    """
    FR-10: Simulated eSewa Payment Integration
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SimulatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_id = serializer.validated_data['order_id']
        simulate_failure = serializer.validated_data.get('simulate_failure', False)
        remarks = serializer.validated_data.get('remarks', 'Simulated eSewa Payment via API')

        try:
            order = Order.objects.get(id=order_id, buyer=request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found or does not belong to you."}, status=status.HTTP_404_NOT_FOUND)

        if order.payment_status == Order.PaymentStatus.PAID:
            return Response({"message": "Order is already paid."}, status=status.HTTP_400_BAD_REQUEST)

        # Generate fake eSewa gateway response dictionary
        tx_code = f"ESEWA-SIM-{uuid.uuid4().hex[:8].upper()}"
        
        if simulate_failure:
            tx_status = PaymentTransaction.Status.FAILED
            gateway_resp = {
                "status": "FAILED",
                "message": "User cancelled or insufficient funds in simulated eSewa wallet.",
                "transaction_code": tx_code
            }
        else:
            tx_status = PaymentTransaction.Status.SUCCESS
            gateway_resp = {
                "status": "SUCCESS",
                "message": "Simulated eSewa payment verified successfully.",
                "transaction_code": tx_code,
                "pid": order.order_reference,
                "amount": float(order.total_amount)
            }

        with transaction.atomic():
            payment_tx = PaymentTransaction.objects.create(
                order=order,
                user=request.user,
                transaction_code=tx_code,
                payment_method='eSewa (Simulated)',
                amount=order.total_amount,
                status=tx_status,
                remarks=remarks,
                gateway_response=gateway_resp
            )

            if tx_status == PaymentTransaction.Status.SUCCESS:
                order.payment_status = Order.PaymentStatus.PAID
                order.status = Order.OrderStatus.CONFIRMED
                order.save()

            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
            log_audit(
                category=AuditLog.Category.PAYMENT,
                action=f"Completed eSewa Payment Rs. {order.total_amount} for Order {order.order_reference}" if tx_status == PaymentTransaction.Status.SUCCESS else f"Failed eSewa Payment attempt for Order {order.order_reference}",
                user=request.user,
                ip_address=ip,
                status=AuditLog.Status.SUCCESS if tx_status == PaymentTransaction.Status.SUCCESS else AuditLog.Status.FAILED,
                metadata={"transaction_code": tx_code, "amount": str(order.total_amount)}
            )

        return Response({
            'status': tx_status,
            'message': gateway_resp['message'],
            'transaction': PaymentTransactionSerializer(payment_tx).data
        }, status=status.HTTP_200_OK if tx_status == PaymentTransaction.Status.SUCCESS else status.HTTP_400_BAD_REQUEST)


class PaymentTransactionListView(generics.ListAPIView):
    serializer_class = PaymentTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'ADMIN':
            return PaymentTransaction.objects.all()
        return PaymentTransaction.objects.filter(user=user)
