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

    def test_negative_stock_rejected_by_serializer(self):
        from .serializers import ProductSerializer
        data = {
            'category': self.cat.id,
            'name': 'Invalid Stock Cement',
            'price': 500.00,
            'available_stock': -5,
            'unit': 'Bag',
            'description': 'Test'
        }
        serializer = ProductSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('available_stock', serializer.errors)

    def test_zero_and_positive_stock_accepted(self):
        from .serializers import ProductSerializer
        data_zero = {
            'category': self.cat.id,
            'name': 'Zero Stock Cement',
            'price': 500.00,
            'available_stock': 0,
            'unit': 'Bag',
            'description': 'Test'
        }
        serializer_zero = ProductSerializer(data=data_zero)
        self.assertTrue(serializer_zero.is_valid(), serializer_zero.errors)

        data_pos = {
            'category': self.cat.id,
            'name': 'Positive Stock Cement',
            'price': 500.00,
            'available_stock': 25,
            'unit': 'Bag',
            'description': 'Test'
        }
        serializer_pos = ProductSerializer(data=data_pos)
        self.assertTrue(serializer_pos.is_valid(), serializer_pos.errors)

    def test_supplier_can_browse_all_active_products(self):
        self.client.force_authenticate(user=self.supplier1)
        res = self.client.get('/api/v1/marketplace/products/')
        self.assertEqual(res.status_code, 200)
        product_ids = [p['id'] for p in res.data['results'] if 'results' in res.data] if isinstance(res.data, dict) else [p['id'] for p in res.data]
        self.assertIn(self.product1.id, product_ids)
        self.assertIn(self.product2.id, product_ids)

    def test_supplier_cannot_edit_other_supplier_product(self):
        self.client.force_authenticate(user=self.supplier1)
        res = self.client.patch(f'/api/v1/marketplace/products/{self.product2.id}/', {'price': 999.00}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_citizen_cannot_modify_product_inventory(self):
        self.client.force_authenticate(user=self.buyer)
        res_create = self.client.post('/api/v1/marketplace/products/', {
            'category': self.cat.id, 'name': 'Citizen Cement', 'price': 100, 'available_stock': 10, 'unit': 'Bag', 'description': 'Illegal'
        }, format='json')
        self.assertEqual(res_create.status_code, 403)

        res_update = self.client.patch(f'/api/v1/marketplace/products/{self.product1.id}/', {'available_stock': 999}, format='json')
        self.assertEqual(res_update.status_code, 403)

    def test_checkout_clears_cart_and_creates_order_and_items(self):
        self.client.force_authenticate(user=self.buyer)
        cart, _ = ShoppingCart.objects.get_or_create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.product1, quantity=5)

        res = self.client.post('/api/v1/marketplace/cart/checkout/', {
            'shipping_address': 'Kathmandu',
            'contact_phone': '9800000000'
        }, format='json')
        self.assertEqual(res.status_code, 201)
        
        # Verify cart is empty
        cart_items_count = cart.items.count()
        self.assertEqual(cart_items_count, 0)

        # Verify order and items
        order_id = res.data['order']['id']
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().product_id, self.product1.id)
        self.assertEqual(order.items.first().quantity, 5)


class MarketplaceLocationTests(TestCase):
    """
    P1: Location-Aware Material Discovery Automated Test Suite (Tests 1-16)
    """
    def setUp(self):
        from locations.models import Province, District, Municipality
        self.client = APIClient()

        # Location Hierarchy
        self.province = Province.objects.create(name='Bagmati Province', code=3)
        self.district = District.objects.create(province=self.province, name='Kathmandu')
        self.muni1 = Municipality.objects.create(
            district=self.district,
            name='Kathmandu Metropolitan City',
            type=Municipality.TypeChoices.METROPOLITAN
        )
        self.muni2 = Municipality.objects.create(
            district=self.district,
            name='Lalitpur Metropolitan City',
            type=Municipality.TypeChoices.METROPOLITAN
        )

        # Users
        self.supplier1 = User.objects.create_user(
            username='loc_supplier1', email='loc_sup1@test.com', password='pass',
            role=User.Role.MATERIAL_SUPPLIER
        )
        self.supplier2 = User.objects.create_user(
            username='loc_supplier2', email='loc_sup2@test.com', password='pass',
            role=User.Role.MATERIAL_SUPPLIER
        )
        self.buyer = User.objects.create_user(
            username='loc_buyer', email='loc_buyer@test.com', password='pass',
            role=User.Role.CITIZEN
        )

        # Categories
        self.cat_cement = ProductCategory.objects.create(name='Cement', slug='loc-cement')
        self.cat_steel = ProductCategory.objects.create(name='Steel', slug='loc-steel')

        # Products: 1 in muni1, 1 in muni2, 1 with no municipality (legacy/general)
        self.prod_muni1 = Product.objects.create(
            supplier=self.supplier1, category=self.cat_cement,
            municipality=self.muni1,
            name='Shivam OPC Cement', price=820.00, available_stock=100,
            unit='Bag', description='High quality OPC', is_active=True
        )
        self.prod_muni2 = Product.objects.create(
            supplier=self.supplier2, category=self.cat_cement,
            municipality=self.muni2,
            name='Maruti PPC Cement', price=750.00, available_stock=80,
            unit='Bag', description='PPC cement', is_active=True
        )
        self.prod_no_muni = Product.objects.create(
            supplier=self.supplier1, category=self.cat_steel,
            municipality=None,
            name='Hama TMT Steel Rebar', price=105.00, available_stock=500,
            unit='Kg', description='Fe 500D TMT', is_active=True
        )

    # 1. Product can be associated with a municipality
    def test_01_product_can_be_associated_with_municipality(self):
        self.assertEqual(self.prod_muni1.municipality, self.muni1)
        self.assertEqual(self.prod_muni1.municipality.name, 'Kathmandu Metropolitan City')
        self.assertEqual(self.prod_muni1.municipality.district.name, 'Kathmandu')

    # 2. Existing products without municipality remain valid
    def test_02_existing_products_without_municipality_remain_valid(self):
        self.assertIsNone(self.prod_no_muni.municipality)
        self.assertTrue(self.prod_no_muni.is_active)
        self.prod_no_muni.price = 110.00
        self.prod_no_muni.save()
        self.prod_no_muni.refresh_from_db()
        self.assertEqual(self.prod_no_muni.price, 110.00)

    # 3. ProductSerializer exposes municipality correctly
    def test_03_product_serializer_exposes_municipality_correctly(self):
        from .serializers import ProductSerializer
        ser_with = ProductSerializer(self.prod_muni1)
        self.assertEqual(ser_with.data['municipality'], self.muni1.id)
        self.assertEqual(ser_with.data['municipality_name'], 'Kathmandu Metropolitan City')
        self.assertEqual(ser_with.data['municipality_district'], 'Kathmandu')
        self.assertEqual(ser_with.data['municipality_province'], 'Bagmati Province')

        ser_without = ProductSerializer(self.prod_no_muni)
        self.assertIsNone(ser_without.data['municipality'])
        self.assertIsNone(ser_without.data['municipality_name'])
        self.assertIsNone(ser_without.data['municipality_district'])
        self.assertIsNone(ser_without.data['municipality_province'])

    # 4. Supplier can assign municipality to their own product
    def test_04_supplier_can_assign_municipality_to_own_product(self):
        self.client.force_authenticate(user=self.supplier1)
        res = self.client.patch(
            f'/api/v1/marketplace/products/{self.prod_no_muni.id}/',
            {'municipality': self.muni1.id},
            format='json'
        )
        self.assertEqual(res.status_code, 200)
        self.prod_no_muni.refresh_from_db()
        self.assertEqual(self.prod_no_muni.municipality, self.muni1)

    # 5. Supplier cannot modify another supplier's product municipality
    def test_05_supplier_cannot_modify_other_supplier_product_municipality(self):
        self.client.force_authenticate(user=self.supplier1)
        res = self.client.patch(
            f'/api/v1/marketplace/products/{self.prod_muni2.id}/',
            {'municipality': self.muni1.id},
            format='json'
        )
        self.assertEqual(res.status_code, 403)
        self.prod_muni2.refresh_from_db()
        self.assertEqual(self.prod_muni2.municipality, self.muni2)

    # 6. Citizen cannot modify product municipality
    def test_06_citizen_cannot_modify_product_municipality(self):
        self.client.force_authenticate(user=self.buyer)
        res = self.client.patch(
            f'/api/v1/marketplace/products/{self.prod_muni1.id}/',
            {'municipality': self.muni2.id},
            format='json'
        )
        self.assertEqual(res.status_code, 403)
        self.prod_muni1.refresh_from_db()
        self.assertEqual(self.prod_muni1.municipality, self.muni1)

    # 7. Municipality filtering returns only matching products
    def test_07_municipality_filtering_returns_only_matching_products(self):
        res = self.client.get(f'/api/v1/marketplace/products/?municipality={self.muni1.id}')
        self.assertEqual(res.status_code, 200)
        data = res.data if isinstance(res.data, list) else res.data.get('results', [])
        ids = [p['id'] for p in data]
        self.assertIn(self.prod_muni1.id, ids)
        self.assertNotIn(self.prod_muni2.id, ids)

    # 8. Products from other municipalities are excluded from a filtered request
    def test_08_products_from_other_municipalities_excluded_from_filtered_request(self):
        res = self.client.get(f'/api/v1/marketplace/products/?municipality={self.muni2.id}')
        self.assertEqual(res.status_code, 200)
        data = res.data if isinstance(res.data, list) else res.data.get('results', [])
        ids = [p['id'] for p in data]
        self.assertIn(self.prod_muni2.id, ids)
        self.assertNotIn(self.prod_muni1.id, ids)
        self.assertNotIn(self.prod_no_muni.id, ids)

    # 9. All-municipality request returns all active products
    def test_09_all_municipality_request_returns_all_active_products(self):
        res = self.client.get('/api/v1/marketplace/products/')
        self.assertEqual(res.status_code, 200)
        data = res.data if isinstance(res.data, list) else res.data.get('results', [])
        ids = [p['id'] for p in data]
        self.assertIn(self.prod_muni1.id, ids)
        self.assertIn(self.prod_muni2.id, ids)
        self.assertIn(self.prod_no_muni.id, ids)

    # 10. Existing search still works
    def test_10_existing_search_still_works(self):
        res = self.client.get('/api/v1/marketplace/products/?search=Shivam')
        self.assertEqual(res.status_code, 200)
        data = res.data if isinstance(res.data, list) else res.data.get('results', [])
        ids = [p['id'] for p in data]
        self.assertIn(self.prod_muni1.id, ids)
        self.assertNotIn(self.prod_muni2.id, ids)

    # 11. Existing category filtering still works
    def test_11_existing_category_filtering_still_works(self):
        res = self.client.get(f'/api/v1/marketplace/products/?category={self.cat_steel.id}')
        self.assertEqual(res.status_code, 200)
        data = res.data if isinstance(res.data, list) else res.data.get('results', [])
        ids = [p['id'] for p in data]
        self.assertIn(self.prod_no_muni.id, ids)
        self.assertNotIn(self.prod_muni1.id, ids)
        self.assertNotIn(self.prod_muni2.id, ids)

    # 12. Municipality + search can work together
    def test_12_municipality_and_search_work_together(self):
        # Match both municipality and search
        res = self.client.get(f'/api/v1/marketplace/products/?municipality={self.muni1.id}&search=Shivam')
        self.assertEqual(res.status_code, 200)
        data = res.data if isinstance(res.data, list) else res.data.get('results', [])
        ids = [p['id'] for p in data]
        self.assertIn(self.prod_muni1.id, ids)

        # Match municipality but search does not match
        res_empty = self.client.get(f'/api/v1/marketplace/products/?municipality={self.muni1.id}&search=NonExistent')
        self.assertEqual(res_empty.status_code, 200)
        data_empty = res_empty.data if isinstance(res_empty.data, list) else res_empty.data.get('results', [])
        self.assertEqual(len(data_empty), 0)

    # 13. Supplier can still browse products from all municipalities
    def test_13_supplier_can_browse_products_from_all_municipalities(self):
        self.client.force_authenticate(user=self.supplier1)
        res = self.client.get('/api/v1/marketplace/products/')
        self.assertEqual(res.status_code, 200)
        data = res.data if isinstance(res.data, list) else res.data.get('results', [])
        ids = [p['id'] for p in data]
        self.assertIn(self.prod_muni1.id, ids)
        self.assertIn(self.prod_muni2.id, ids)
        self.assertIn(self.prod_no_muni.id, ids)

    # 14. Existing checkout still works
    def test_14_existing_checkout_still_works(self):
        self.client.force_authenticate(user=self.buyer)
        cart, _ = ShoppingCart.objects.get_or_create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.prod_muni1, quantity=2)

        res = self.client.post('/api/v1/marketplace/cart/checkout/', {
            'shipping_address': 'Kathmandu Ward 4',
            'contact_phone': '9841234567'
        }, format='json')
        self.assertEqual(res.status_code, 201)
        self.prod_muni1.refresh_from_db()
        self.assertEqual(self.prod_muni1.available_stock, 98)

    # 15. Existing simulated payment still works
    def test_15_existing_simulated_payment_still_works(self):
        self.client.force_authenticate(user=self.buyer)
        cart, _ = ShoppingCart.objects.get_or_create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.prod_muni1, quantity=1)

        res_checkout = self.client.post('/api/v1/marketplace/cart/checkout/', {
            'shipping_address': 'Kathmandu Ward 4',
            'contact_phone': '9841234567'
        }, format='json')
        self.assertEqual(res_checkout.status_code, 201)
        order_id = res_checkout.data['order']['id']

        # Simulate eSewa payment
        res_pay = self.client.post('/api/v1/payments/esewa/simulate/', {
            'order_id': order_id,
            'simulate_failure': False
        }, format='json')
        self.assertEqual(res_pay.status_code, 200)
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(order.status, Order.OrderStatus.CONFIRMED)

    # 16. Existing order lifecycle still works
    def test_16_existing_order_lifecycle_still_works(self):
        self.client.force_authenticate(user=self.buyer)
        cart, _ = ShoppingCart.objects.get_or_create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.prod_muni1, quantity=1)

        res_checkout = self.client.post('/api/v1/marketplace/cart/checkout/', {
            'shipping_address': 'Kathmandu Ward 4',
            'contact_phone': '9841234567'
        }, format='json')
        order_id = res_checkout.data['order']['id']

        # Pay order
        self.client.post('/api/v1/payments/esewa/simulate/', {'order_id': order_id, 'simulate_failure': False}, format='json')

        # Supplier progresses lifecycle: CONFIRMED -> PROCESSING -> SHIPPED -> DELIVERED
        self.client.force_authenticate(user=self.supplier1)
        res_proc = self.client.patch(f'/api/v1/marketplace/orders/{order_id}/', {'status': 'PROCESSING'}, format='json')
        self.assertEqual(res_proc.status_code, 200)

        res_ship = self.client.patch(f'/api/v1/marketplace/orders/{order_id}/', {'status': 'SHIPPED'}, format='json')
        self.assertEqual(res_ship.status_code, 200)

        res_deliv = self.client.patch(f'/api/v1/marketplace/orders/{order_id}/', {'status': 'DELIVERED'}, format='json')
        self.assertEqual(res_deliv.status_code, 200)

        order = Order.objects.get(id=order_id)
        self.assertIn(order.status, (Order.OrderStatus.DELIVERED, Order.OrderStatus.COMPLETED))