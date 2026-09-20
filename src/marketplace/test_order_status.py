from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from .models import ProductCategory, Product, ShoppingCart, CartItem, Order, OrderItem

User = get_user_model()

class MarketplaceLifecycleSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.supplier1 = User.objects.create_user(username='supplier1', email='supplier1@test.com', password='pass', role=User.Role.MATERIAL_SUPPLIER)
        self.supplier2 = User.objects.create_user(username='supplier2', email='supplier2@test.com', password='pass', role=User.Role.MATERIAL_SUPPLIER)
        self.buyer = User.objects.create_user(username='buyer1', email='buyer1@test.com', password='pass', role=User.Role.CITIZEN)

        self.cat = ProductCategory.objects.create(name='Cement', slug='cement')
        self.product1 = Product.objects.create(
            supplier=self.supplier1, category=self.cat, name='Shivam Cement',
            price=800.00, available_stock=100, unit='Bag', description='OPC', is_active=True
        )
        self.product2 = Product.objects.create(
            supplier=self.supplier2, category=self.cat, name='Maruti Cement',
            price=750.00, available_stock=50, unit='Bag', description='PPC', is_active=True
        )

    def test_insufficient_stock_returns_400_not_500(self):
        self.client.force_authenticate(user=self.buyer)
        cart, _ = ShoppingCart.objects.get_or_create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.product1, quantity=150) # Exceeds 100 stock

        res = self.client.post('/api/v1/marketplace/cart/checkout/', {
            'shipping_address': 'Baneshwor',
            'contact_phone': '9841111111'
        }, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('Insufficient stock', str(res.data))

    def test_successful_checkout_deducts_stock(self):
        self.client.force_authenticate(user=self.buyer)
        cart, _ = ShoppingCart.objects.get_or_create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.product1, quantity=10)

        res = self.client.post('/api/v1/marketplace/cart/checkout/', {
            'shipping_address': 'Baneshwor',
            'contact_phone': '9841111111'
        }, format='json')
        self.assertEqual(res.status_code, 201)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.available_stock, 90)

    def test_customer_cancellation_restores_stock(self):
        self.client.force_authenticate(user=self.buyer)
        cart, _ = ShoppingCart.objects.get_or_create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.product1, quantity=10)

        res = self.client.post('/api/v1/marketplace/cart/checkout/', {
            'shipping_address': 'Baneshwor',
            'contact_phone': '9841111111'
        }, format='json')
        self.assertEqual(res.status_code, 201)
        order_id = res.data['order']['id']
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.available_stock, 90)

        # Cancel order
        cancel_res = self.client.post(f'/api/v1/marketplace/orders/{order_id}/cancel/')
        self.assertEqual(cancel_res.status_code, 200)

        self.product1.refresh_from_db()
        self.assertEqual(self.product1.available_stock, 100)
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, Order.OrderStatus.CANCELLED)

    def test_unpaid_order_cannot_be_processed_or_shipped(self):
        order = Order.objects.create(
            buyer=self.buyer, total_amount=800, shipping_address='Addr', contact_phone='123',
            status=Order.OrderStatus.PENDING, payment_status=Order.PaymentStatus.UNPAID
        )
        OrderItem.objects.create(
            order=order, product=self.product1, supplier=self.supplier1, product_name=self.product1.name,
            quantity=1, unit_price=800, subtotal=800, status=Order.OrderStatus.PENDING
        )

        self.client.force_authenticate(user=self.supplier1)
        res = self.client.patch(f'/api/v1/marketplace/orders/{order.id}/', {'status': 'PROCESSING'}, format='json')
        self.assertEqual(res.status_code, 400)

        res_ship = self.client.patch(f'/api/v1/marketplace/orders/{order.id}/', {'status': 'SHIPPED'}, format='json')
        self.assertEqual(res_ship.status_code, 400)

    def test_valid_supplier_order_lifecycle(self):
        # Order is paid
        order = Order.objects.create(
            buyer=self.buyer, total_amount=800, shipping_address='Addr', contact_phone='123',
            status=Order.OrderStatus.CONFIRMED, payment_status=Order.PaymentStatus.PAID
        )
        item = OrderItem.objects.create(
            order=order, product=self.product1, supplier=self.supplier1, product_name=self.product1.name,
            quantity=1, unit_price=800, subtotal=800, status=Order.OrderStatus.CONFIRMED
        )

        self.client.force_authenticate(user=self.supplier1)

        # 1. CONFIRMED -> PROCESSING
        res = self.client.patch(f'/api/v1/marketplace/orders/{order.id}/', {'status': 'PROCESSING'}, format='json')
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.OrderStatus.PROCESSING)

        # 2. PROCESSING -> SHIPPED
        res = self.client.patch(f'/api/v1/marketplace/orders/{order.id}/', {'status': 'SHIPPED'}, format='json')
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.OrderStatus.SHIPPED)

        # 3. SHIPPED -> DELIVERED
        res = self.client.patch(f'/api/v1/marketplace/orders/{order.id}/', {'status': 'DELIVERED'}, format='json')
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertIn(order.status, (Order.OrderStatus.DELIVERED, Order.OrderStatus.COMPLETED))

    def test_invalid_status_transitions_rejected(self):
        order = Order.objects.create(
            buyer=self.buyer, total_amount=800, shipping_address='Addr', contact_phone='123',
            status=Order.OrderStatus.CONFIRMED, payment_status=Order.PaymentStatus.PAID
        )
        OrderItem.objects.create(
            order=order, product=self.product1, supplier=self.supplier1, product_name=self.product1.name,
            quantity=1, unit_price=800, subtotal=800, status=Order.OrderStatus.CONFIRMED
        )

        self.client.force_authenticate(user=self.supplier1)

        # CONFIRMED -> SHIPPED is invalid (must go through PROCESSING)
        res = self.client.patch(f'/api/v1/marketplace/orders/{order.id}/', {'status': 'SHIPPED'}, format='json')
        self.assertEqual(res.status_code, 400)

        # CONFIRMED -> DELIVERED is invalid
        res = self.client.patch(f'/api/v1/marketplace/orders/{order.id}/', {'status': 'DELIVERED'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_supplier_isolation(self):
        order = Order.objects.create(
            buyer=self.buyer, total_amount=1550, shipping_address='Addr', contact_phone='123',
            status=Order.OrderStatus.CONFIRMED, payment_status=Order.PaymentStatus.PAID
        )
        item1 = OrderItem.objects.create(
            order=order, product=self.product1, supplier=self.supplier1, product_name=self.product1.name,
            quantity=1, unit_price=800, subtotal=800, status=Order.OrderStatus.CONFIRMED
        )
        item2 = OrderItem.objects.create(
            order=order, product=self.product2, supplier=self.supplier2, product_name=self.product2.name,
            quantity=1, unit_price=750, subtotal=750, status=Order.OrderStatus.CONFIRMED
        )

        # Supplier 1 views order
        self.client.force_authenticate(user=self.supplier1)
        res = self.client.get(f'/api/v1/marketplace/orders/{order.id}/')
        self.assertEqual(res.status_code, 200)
        items = res.data['items']
        # Supplier 1 only sees their item, not Supplier 2's item
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['product_name'], self.product1.name)

        # Supplier 2 cannot modify Supplier 1's items or an order where they have no items
        other_order = Order.objects.create(
            buyer=self.buyer, total_amount=800, shipping_address='Addr', contact_phone='123',
            status=Order.OrderStatus.CONFIRMED, payment_status=Order.PaymentStatus.PAID
        )
        OrderItem.objects.create(
            order=other_order, product=self.product1, supplier=self.supplier1, product_name=self.product1.name,
            quantity=1, unit_price=800, subtotal=800, status=Order.OrderStatus.CONFIRMED
        )

        self.client.force_authenticate(user=self.supplier2)
        res_unauth = self.client.patch(f'/api/v1/marketplace/orders/{other_order.id}/', {'status': 'PROCESSING'}, format='json')
        self.assertIn(res_unauth.status_code, (403, 404))

    def test_supplier_can_view_inactive_products(self):
        # Create an inactive product for supplier1
        inactive_prod = Product.objects.create(
            supplier=self.supplier1, category=self.cat, name='Old Cement',
            price=700.00, available_stock=0, unit='Bag', description='Discontinued', is_active=False
        )

        # Authenticated as supplier1: should return active + inactive products for supplier1
        self.client.force_authenticate(user=self.supplier1)
        res = self.client.get(f'/api/v1/marketplace/products/?supplier={self.supplier1.id}')
        self.assertEqual(res.status_code, 200)
        product_ids = [p['id'] for p in res.data]
        self.assertIn(inactive_prod.id, product_ids)
        self.assertIn(self.product1.id, product_ids)

        # Authenticated as citizen: inactive product should be hidden
        self.client.force_authenticate(user=self.buyer)
        res_buyer = self.client.get(f'/api/v1/marketplace/products/?supplier={self.supplier1.id}')
        self.assertEqual(res_buyer.status_code, 200)
        buyer_prod_ids = [p['id'] for p in res_buyer.data]
        self.assertNotIn(inactive_prod.id, buyer_prod_ids)
        self.assertIn(self.product1.id, buyer_prod_ids)