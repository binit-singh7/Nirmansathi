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
    municipality_name = serializers.SerializerMethodField()
    municipality_district = serializers.SerializerMethodField()
    municipality_province = serializers.SerializerMethodField()

    def get_municipality_name(self, obj):
        return obj.municipality.name if obj.municipality else None

    def get_municipality_district(self, obj):
        return obj.municipality.district.name if obj.municipality and obj.municipality.district else None

    def get_municipality_province(self, obj):
        if obj.municipality and obj.municipality.district and obj.municipality.district.province:
            return obj.municipality.district.province.name
        return None

    class Meta:
        model = Product
        fields = [
            'id', 'supplier', 'supplier_name', 'supplier_company',
            'category', 'category_name', 'municipality', 'municipality_name',
            'municipality_district', 'municipality_province',
            'name', 'price', 'available_stock', 'unit', 'description', 'image',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'supplier', 'created_at', 'updated_at']

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate_available_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Available stock cannot be negative.")
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
    status_display = serializers.ReadOnlyField(source='get_status_display')

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'supplier', 'product_name',
            'quantity', 'unit_price', 'subtotal', 'status', 'status_display'
        ]
        read_only_fields = ['id', 'product', 'supplier', 'product_name', 'quantity', 'unit_price', 'subtotal']


class OrderSerializer(serializers.ModelSerializer):
    buyer_name = serializers.ReadOnlyField(source='buyer.username')
    status_display = serializers.SerializerMethodField()
    payment_status_display = serializers.ReadOnlyField(source='get_payment_status_display')
    items = serializers.SerializerMethodField()
    supplier_status = serializers.SerializerMethodField()
    supplier_status_display = serializers.SerializerMethodField()
    supplier_total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_reference', 'buyer', 'buyer_name',
            'status', 'status_display', 'payment_status', 'payment_status_display',
            'total_amount', 'shipping_address', 'contact_phone',
            'items', 'created_at', 'updated_at',
            'supplier_status', 'supplier_status_display', 'supplier_total_amount'
        ]
        read_only_fields = [
            'id', 'order_reference', 'buyer', 'payment_status',
            'total_amount', 'created_at', 'updated_at'
        ]

    def get_status_display(self, obj):
        if obj.status in (Order.OrderStatus.COMPLETED, Order.OrderStatus.DELIVERED):
            return 'Delivered'
        return obj.get_status_display()

    def _get_supplier_items(self, obj):
        request = self.context.get('request')
        queryset = obj.items.all()
        if request and request.user and request.user.is_authenticated:
            if request.user.is_material_supplier and not (request.user.is_staff or getattr(request.user, 'role', None) == 'ADMIN'):
                return queryset.filter(supplier=request.user)
        return queryset

    def get_supplier_status(self, obj):
        supplier_items = self._get_supplier_items(obj)
        if supplier_items.exists():
            statuses = list(supplier_items.values_list('status', flat=True))
            if all(s in (Order.OrderStatus.COMPLETED, Order.OrderStatus.DELIVERED) for s in statuses):
                return Order.OrderStatus.DELIVERED
            elif any(s == Order.OrderStatus.SHIPPED for s in statuses):
                return Order.OrderStatus.SHIPPED
            elif any(s == Order.OrderStatus.PROCESSING for s in statuses):
                return Order.OrderStatus.PROCESSING
            elif all(s == Order.OrderStatus.CONFIRMED for s in statuses):
                return Order.OrderStatus.CONFIRMED
            elif all(s == Order.OrderStatus.CANCELLED for s in statuses):
                return Order.OrderStatus.CANCELLED
            return statuses[0]
        return obj.status

    def get_supplier_status_display(self, obj):
        st = self.get_supplier_status(obj)
        if st in (Order.OrderStatus.COMPLETED, Order.OrderStatus.DELIVERED):
            return 'Delivered'
        return dict(Order.OrderStatus.choices).get(st, st)

    def get_supplier_total_amount(self, obj):
        supplier_items = self._get_supplier_items(obj)
        return float(sum(item.subtotal for item in supplier_items))

    def get_items(self, obj):
        queryset = self._get_supplier_items(obj)
        return OrderItemSerializer(queryset, many=True).data

