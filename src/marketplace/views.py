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
                if item.quantity > product.available_stock:
                    raise ValueError(f"Insufficient stock for {product.name}.")

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    supplier=product.supplier,
                    product_name=product.name,
                    quantity=item.quantity,
                    unit_price=product.price,
                    subtotal=item.get_subtotal()
                )

                # Deduct stock
                product.available_stock -= item.quantity
                product.save()

            # Clear cart
            cart_items.delete()

        return Response({
            'message': 'Order placed successfully.',
            'order': OrderSerializer(order).data
        }, status=status.HTTP_201_CREATED)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'patch', 'head', 'options']  # Disable POST/PUT/DELETE on this viewset

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'ADMIN':
            return Order.objects.all()
        if user.is_material_supplier:
            # Orders containing products supplied by this user
            return Order.objects.filter(items__supplier=user).distinct()
        return Order.objects.filter(buyer=user)

    def partial_update(self, request, *args, **kwargs):
        """Allow suppliers and admins to update the order status only."""
        user = request.user
        if not (user.is_staff or getattr(user, 'role', None) == 'ADMIN' or user.is_material_supplier):
            return Response(
                {"error": "Only suppliers or admins can update order status."},
                status=status.HTTP_403_FORBIDDEN
            )
        # Restrict updatable fields to status only
        allowed_fields = {'status'}
        data = {k: v for k, v in request.data.items() if k in allowed_fields}
        if not data:
            return Response({"error": "No valid fields to update. Only 'status' is allowed."},
                            status=status.HTTP_400_BAD_REQUEST)
        if 'status' in data and data['status'] not in Order.OrderStatus.values:
            return Response({"error": "Invalid status value."}, status=status.HTTP_400_BAD_REQUEST)

        kwargs['partial'] = True
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, pk=None):
        """Legacy POST endpoint kept for compatibility."""
        order = self.get_object()
        user = request.user
        if not (user.is_staff or getattr(user, 'role', None) == 'ADMIN' or user.is_material_supplier):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        new_status = request.data.get('status')
        if new_status not in Order.OrderStatus.values:
            return Response({"error": "Invalid status value."}, status=status.HTTP_400_BAD_REQUEST)

        order.status = new_status
        order.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)
