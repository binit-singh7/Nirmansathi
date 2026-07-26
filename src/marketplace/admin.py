from django.contrib import admin
from .models import ProductCategory, Product, ShoppingCart, CartItem, Order, OrderItem

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'supplier', 'product_name', 'quantity', 'unit_price', 'subtotal')

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'supplier', 'category', 'price', 'unit', 'available_stock', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'description', 'supplier__username')

@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_total_price', 'updated_at')
    inlines = [CartItemInline]

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_reference', 'buyer', 'total_amount', 'status', 'payment_status', 'created_at')
    list_filter = ('status', 'payment_status')
    search_fields = ('order_reference', 'buyer__username', 'contact_phone')
    inlines = [OrderItemInline]
