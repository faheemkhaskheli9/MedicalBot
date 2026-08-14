from rest_framework.permissions import BasePermission


class IsHospitalAdmin(BasePermission):
    """Allow access only to staff users or users with role=hospital_admin."""

    message = "Only hospital administrators can access this resource."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or getattr(request.user, "role", None) == "hospital_admin")
        )
