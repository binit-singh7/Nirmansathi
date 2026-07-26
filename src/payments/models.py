import uuid
from django.db import models
from django.conf import settings

def generate_transaction_code():
    return f"ESEWA-SIM-{uuid.uuid4().hex[:10].upper()}"

class PaymentTransaction(models.Model):
    class Status(models.TextChoices):
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'
        PENDING = 'PENDING', 'Pending'

    order = models.ForeignKey(
        'marketplace.Order',
        on_delete=models.CASCADE,
        related_name='payment_transactions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_transactions'
    )
    transaction_code = models.CharField(
        max_length=100,
        unique=True,
        default=generate_transaction_code
    )
    payment_method = models.CharField(max_length=50, default='eSewa (Simulated)')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    remarks = models.CharField(max_length=255, blank=True, null=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_code} - {self.status} (NPR {self.amount})"
