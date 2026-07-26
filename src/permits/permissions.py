from rest_framework import permissions

class IsPermitParticipant(permissions.BasePermission):
    """
    Custom permission for Permit Applications:
    - Citizens can create applications and view/manage ONLY their own applications.
    - Municipality Officers can view and issue decisions for applications in THEIR municipality.
    - Staff / Admins have full access.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_staff or user.role == 'ADMIN':
            return True

        if user.is_citizen:
            return obj.applicant == user

        if user.is_municipality_officer:
            if user.municipality:
                return obj.municipality == user.municipality
            return True

        return False
