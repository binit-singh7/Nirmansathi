from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from .models import ProductCategory, Product, Order, OrderItem

User = get_user_model()

class OrderStatusUpdateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Create users
        self.supplier = User.objects.create_user(username='supplier1', email='supplier1@example.com', password='pass', role=User.Role.MATERIAL_SUPPLIER)
        self.other_supplier = User.objects.create_user(username='supplier2', email='supplier2@example.com', password='pass', role=User.Role.MATERIAL_SUPPLIER)
        self.buyer = User.objects.create_user(username='buyer1', email='buyer1@example.com', password='pass', role=User.Role.CITIZEN)

        # Category & Product
        self.cat = ProductCategory.objects.create(name='Cement', slug='cement')
        self.product = Product.objects.create(
            supplier=self.supplier,
            category=self.cat,
            name='Cement Bag',
            price=100.00,
            available_stock=10,
            unit='Bag',
            description='Test cement',
            is_active=True
        )

        # Order created by buyer
        self.order = Order.objects.create(
            buyer=self.buyer,
            total_amount=100.00,
            shipping_address='Some Address',
            contact_phone='9999',
            status=Order.OrderStatus.PENDING,
            payment_status=Order.PaymentStatus.UNPAID
        )

        # OrderItem linking supplier to order
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            supplier=self.supplier,
            product_name=self.product.name,
            quantity=1,
            unit_price=self.product.price,
            subtotal=self.product.price
        )

    def test_authorized_supplier_can_update_order(self):
        self.client.force_authenticate(user=self.supplier)
        url = f'/api/v1/marketplace/orders/{self.order.id}/update-status/'
        res = self.client.post(url, {'status': 'SHIPPED'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'SHIPPED')

    def test_unauthorized_supplier_cannot_update_order(self):
        self.client.force_authenticate(user=self.other_supplier)
        url = f'/api/v1/marketplace/orders/{self.order.id}/update-status/'
        res = self.client.post(url, {'status': 'SHIPPED'}, format='json')
        # Should be 404 because queryset filters orders to only those containing supplier's items
        self.assertEqual(res.status_code, 404)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'PENDING')

    def test_invalid_status_rejected(self):
        self.client.force_authenticate(user=self.supplier)
        url = f'/api/v1/marketplace/orders/{self.order.id}/update-status/'
        res = self.client.post(url, {'status': 'INVALID_STATUS'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_patch_on_order_is_not_allowed(self):
        self.client.force_authenticate(user=self.supplier)
        url = f'/api/v1/marketplace/orders/{self.order.id}/'
        res = self.client.patch(url, {'status': 'SHIPPED'}, format='json')
        self.assertIn(res.status_code, (405, 403))