from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction

from .models import (
    ProductCategory,
    Product,
    ShoppingCart,
    CartItem,
    Order,
    OrderItem
)
from .serializers import (
    ProductCategorySerializer,
    ProductSerializer,
    ShoppingCartSerializer,
    CartItemSerializer,
    OrderSerializer
)
from .permissions import IsSupplierOrReadOnly

class ProductCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    permission_classes = [permissions.AllowAny]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('supplier', 'category').filter(is_active=True)
    serializer_class = ProductSerializer
    permission_classes = [IsSupplierOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'category__name', 'supplier__username']
    ordering_fields = ['price', 'created_at', 'available_stock']

    def get_queryset(self):
        queryset = super().get_queryset()
        category_id = self.request.query_params.get('category')
        supplier_id = self.request.query_params.get('supplier')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(supplier=self.request.user)


class ShoppingCartViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        cart, _ = ShoppingCart.objects.get_or_create(user=request.user)
        serializer = ShoppingCartSerializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='add-item')
    def add_item(self, request):
        cart, _ = ShoppingCart.objects.get_or_create(user=request.user)
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))

        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        if quantity > product.available_stock:
            return Response(
                {"error": f"Only {product.available_stock} units available in stock."},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        if not created:
            new_qty = cart_item.quantity + quantity
            if new_qty > product.available_stock:
                return Response(
                    {"error": f"Total quantity ({new_qty}) exceeds stock ({product.available_stock})."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            cart_item.quantity = new_qty
            cart_item.save()
        else:
            cart_item.quantity = quantity
            cart_item.save()

        return Response(ShoppingCartSerializer(cart).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], url_path=r'remove-item/(?P<item_id>\d+)')
    def remove_item(self, request, item_id=None):
        cart, _ = ShoppingCart.objects.get_or_create(user=request.user)
        try:
            item = CartItem.objects.get(id=item_id, cart=cart)
            item.delete()
            return Response(ShoppingCartSerializer(cart).data, status=status.HTTP_200_OK)
        except CartItem.DoesNotExist:
            return Response({"error": "Item not found in cart."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='checkout')
    def checkout(self, request):
        """
        Converts active shopping cart into an Order (FR-11)
        """
        cart, _ = ShoppingCart.objects.get_or_create(user=request.user)
        cart_items = cart.items.select_related('product').all()

        if not cart_items.exists():
            return Response({"error": "Shopping cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        shipping_address = request.data.get('shipping_address')
        contact_phone = request.data.get('contact_phone')

        if not shipping_address or not contact_phone:
            return Response(
                {"error": "Shipping address and contact phone are required for checkout."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate stock for all items before initiating order
        for item in cart_items:
            product = item.product
            if item.quantity > product.available_stock:
                return Response(
                    {"error": f"Insufficient stock for '{product.name}'. Requested {item.quantity}, but only {product.available_stock} available."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        total_amount = cart.get_total_price()

        with transaction.atomic():
            order = Order.objects.create(
                buyer=request.user,
                total_amount=total_amount,
                shipping_address=shipping_address,
                contact_phone=contact_phone,
                status=Order.OrderStatus.PENDING,
                payment_status=Order.PaymentStatus.UNPAID
            )

            for item in cart_items:
                product = item.product
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    supplier=product.supplier,
                    product_name=product.name,
                    quantity=item.quantity,
                    unit_price=product.price,
                    subtotal=item.get_subtotal(),
                    status=Order.OrderStatus.PENDING
                )

                # Deduct stock
                product.available_stock -= item.quantity
                product.save(update_fields=['available_stock'])

            # Clear cart
            cart_items.delete()

        return Response({
            'message': 'Order placed successfully.',
            'order': OrderSerializer(order, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)


VALID_TRANSITIONS = {
    Order.OrderStatus.PENDING: [Order.OrderStatus.CONFIRMED, Order.OrderStatus.CANCELLED],
    Order.OrderStatus.CONFIRMED: [Order.OrderStatus.PROCESSING, Order.OrderStatus.CANCELLED],
    Order.OrderStatus.PROCESSING: [Order.OrderStatus.SHIPPED, Order.OrderStatus.CANCELLED],
    Order.OrderStatus.SHIPPED: [Order.OrderStatus.DELIVERED, Order.OrderStatus.COMPLETED],
    Order.OrderStatus.DELIVERED: [],
    Order.OrderStatus.COMPLETED: [],
    Order.OrderStatus.CANCELLED: [],
}

def restore_order_stock(order_or_items):
    """Restores deducted stock when order or items are cancelled."""
    if isinstance(order_or_items, Order):
        items = order_or_items.items.select_related('product').all()
    else:
        items = order_or_items
    for item in items:
        if item.product:
            item.product.available_stock += item.quantity
            item.product.save(update_fields=['available_stock'])

def recalculate_order_status(order):
    """Aggregates item-level statuses to determine order-level status."""
    items = order.items.all()
    if not items.exists():
        return
    statuses = set(items.values_list('status', flat=True))
    if statuses == {Order.OrderStatus.CANCELLED}:
        order.status = Order.OrderStatus.CANCELLED
    elif all(s in (Order.OrderStatus.DELIVERED, Order.OrderStatus.COMPLETED) for s in statuses):
        order.status = Order.OrderStatus.DELIVERED
    elif any(s == Order.OrderStatus.SHIPPED for s in statuses):
        order.status = Order.OrderStatus.SHIPPED
    elif any(s == Order.OrderStatus.PROCESSING for s in statuses):
        order.status = Order.OrderStatus.PROCESSING
    elif all(s == Order.OrderStatus.CONFIRMED for s in statuses):
        order.status = Order.OrderStatus.CONFIRMED
    order.save(update_fields=['status', 'updated_at'])


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'ADMIN':
            return Order.objects.all()
        if user.is_material_supplier:
            return Order.objects.filter(items__supplier=user).distinct()
        return Order.objects.filter(buyer=user)

    def partial_update(self, request, *args, **kwargs):
        """Allow suppliers and admins to update order fulfillment status."""
        order = self.get_object()
        user = request.user

        if not (user.is_staff or getattr(user, 'role', None) == 'ADMIN' or user.is_material_supplier):
            return Response(
                {"error": "Only suppliers or admins can update order status."},
                status=status.HTTP_403_FORBIDDEN
            )

        new_status = request.data.get('status')
        if not new_status:
            return Response({"error": "Field 'status' is required."}, status=status.HTTP_400_BAD_REQUEST)
        if new_status not in Order.OrderStatus.values:
            return Response({"error": "Invalid status value."}, status=status.HTTP_400_BAD_REQUEST)

        # Map DELIVERED/COMPLETED
        target_status = new_status

        if user.is_material_supplier and not (user.is_staff or getattr(user, 'role', None) == 'ADMIN'):
            supplier_items = order.items.filter(supplier=user)
            if not supplier_items.exists():
                return Response({"error": "You do not supply any items in this order."}, status=status.HTTP_403_FORBIDDEN)

            current_status = supplier_items.first().status or order.status

            # Disallow processing unpaid orders
            if target_status in [Order.OrderStatus.PROCESSING, Order.OrderStatus.SHIPPED, Order.OrderStatus.DELIVERED, Order.OrderStatus.COMPLETED]:
                if order.payment_status != Order.PaymentStatus.PAID:
                    return Response({"error": "Cannot fulfill or process an unpaid order. Payment must be confirmed first."},
                                    status=status.HTTP_400_BAD_REQUEST)

            # Check transition validity
            if target_status not in VALID_TRANSITIONS.get(current_status, []):
                return Response(
                    {"error": f"Invalid status transition from {current_status} to {target_status}."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            with transaction.atomic():
                supplier_items.update(status=target_status)
                if target_status == Order.OrderStatus.CANCELLED:
                    restore_order_stock(supplier_items)
                recalculate_order_status(order)

            return Response(OrderSerializer(order, context={'request': request}).data, status=status.HTTP_200_OK)

        # Admin / Staff update
        current_status = order.status
        if target_status in [Order.OrderStatus.PROCESSING, Order.OrderStatus.SHIPPED, Order.OrderStatus.DELIVERED, Order.OrderStatus.COMPLETED]:
            if order.payment_status != Order.PaymentStatus.PAID:
                return Response({"error": "Cannot fulfill or process an unpaid order. Payment must be confirmed first."},
                                status=status.HTTP_400_BAD_REQUEST)

        if target_status not in VALID_TRANSITIONS.get(current_status, []):
            return Response(
                {"error": f"Invalid status transition from {current_status} to {target_status}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            order.status = target_status
            order.save(update_fields=['status', 'updated_at'])
            order.items.all().update(status=target_status)
            if target_status == Order.OrderStatus.CANCELLED:
                restore_order_stock(order)

        return Response(OrderSerializer(order, context={'request': request}).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, pk=None):
        """Status update action (for forms or compatibility)."""
        return self.partial_update(request, pk=pk)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """Customer or Admin order cancellation with inventory replenishment."""
        order = self.get_object()
        user = request.user

        if user == order.buyer:
            if order.status != Order.OrderStatus.PENDING:
                return Response(
                    {"error": "Only pending orders can be cancelled by the customer."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif not (user.is_staff or getattr(user, 'role', None) == 'ADMIN'):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        if order.status == Order.OrderStatus.CANCELLED:
            return Response({"error": "Order is already cancelled."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            restore_order_stock(order)
            order.status = Order.OrderStatus.CANCELLED
            order.save(update_fields=['status', 'updated_at'])
            order.items.all().update(status=Order.OrderStatus.CANCELLED)

        return Response({
            "message": "Order cancelled successfully and inventory restored.",
            "order": OrderSerializer(order, context={'request': request}).data
        }, status=status.HTTP_200_OK)
