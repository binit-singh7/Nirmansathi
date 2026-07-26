from rest_framework import serializers
from .models import (
    ProductCategory,
    Product,
    ShoppingCart,
    CartItem,
    Order,
    OrderItem
)

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ['id', 'name', 'slug', 'description', 'image']


class ProductSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source='supplier.username')
    supplier_company = serializers.ReadOnlyField(source='supplier.profile.company_name')
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = Product
        fields = [
            'id', 'supplier', 'supplier_name', 'supplier_company',
            'category', 'category_name', 'name', 'price',
            'available_stock', 'unit', 'description', 'image',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'supplier', 'created_at', 'updated_at']

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value


class CartItemSerializer(serializers.ModelSerializer):
    product_detail = ProductSerializer(source='product', read_only=True)
    subtotal = serializers.ReadOnlyField(source='get_subtotal')

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_detail', 'quantity', 'subtotal', 'added_at']

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value


class ShoppingCartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.ReadOnlyField(source='get_total_price')

    class Meta:
        model = ShoppingCart
        fields = ['id', 'user', 'items', 'total_price', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'supplier', 'product_name', 'quantity', 'unit_price', 'subtotal']


class OrderSerializer(serializers.ModelSerializer):
    buyer_name = serializers.ReadOnlyField(source='buyer.username')
    status_display = serializers.ReadOnlyField(source='get_status_display')
    payment_status_display = serializers.ReadOnlyField(source='get_payment_status_display')
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_reference', 'buyer', 'buyer_name',
            'status', 'status_display', 'payment_status', 'payment_status_display',
            'total_amount', 'shipping_address', 'contact_phone',
            'items', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'order_reference', 'buyer', 'status', 'payment_status',
            'total_amount', 'created_at', 'updated_at'
        ]
