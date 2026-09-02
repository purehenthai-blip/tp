from rest_framework import permissions

class IsVendor(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['vendor', 'admin', 'super_admin']

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['admin', 'super_admin']

class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role in ['admin', 'super_admin']:
            return True
        owner = getattr(obj, 'user', getattr(obj, 'buyer', getattr(obj, 'owner', None)))
        return owner == request.user
