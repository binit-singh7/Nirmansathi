from rest_framework import permissions

class IsSupplierOrReadOnly(permissions.BasePermission):
    """
    Custom permission for Marketplace Products:
    - Anyone can list or retrieve products.
    - Only users with role MATERIAL_SUPPLIER or staff/admin can create products.
    - Suppliers can only edit/delete products they own.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and (
            request.user.is_material_supplier or request.user.is_staff or request.user.role == 'ADMIN'
        )

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_staff or request.user.role == 'ADMIN':
            return True
        return obj.supplier == request.user
