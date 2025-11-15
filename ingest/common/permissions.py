from rest_framework import permissions
from ingest.apps.documents.enums import DocumentStatus, QAStatus


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner of the object.
        return obj.created_by == request.user


class CanEditDocument(permissions.BasePermission):
    """
    Permission to check if user can edit a document based on status and role.
    """

    def has_object_permission(self, request, view, obj):
        # Superuser can do anything
        if request.user.is_superuser:
            return True

        # Read permissions for everyone
        if request.method in permissions.SAFE_METHODS:
            return True

        # Approved documents are read-only except for admins
        if obj.status == DocumentStatus.APPROVED:
            return request.user.groups.filter(name='Admin').exists()

        # Operators can only edit their own documents
        if request.user.groups.filter(name='Operator').exists():
            return obj.created_by == request.user

        # Reviewers and admins can edit any non-approved document
        return request.user.groups.filter(name__in=['Reviewer', 'Admin']).exists()


class CanEditQAEntry(permissions.BasePermission):
    """
    Permission to check if user can edit a QA entry based on status and role.
    """

    def has_object_permission(self, request, view, obj):
        # Superuser can do anything
        if request.user.is_superuser:
            return True

        # Read permissions for everyone
        if request.method in permissions.SAFE_METHODS:
            return True

        # Approved QA entries are read-only except for admins
        if obj.status == QAStatus.APPROVED:
            return request.user.groups.filter(name='Admin').exists()

        # Operators can only edit their own QA entries
        if request.user.groups.filter(name='Operator').exists():
            return obj.created_by == request.user

        # Reviewers and admins can edit any non-approved QA entry
        return request.user.groups.filter(name__in=['Reviewer', 'Admin']).exists()


class CanApprove(permissions.BasePermission):
    """
    Permission to check if user can approve documents/QA entries.
    """

    def has_permission(self, request, view):
        return request.user.groups.filter(name__in=['Reviewer', 'Admin']).exists()


class IsOperatorOrAbove(permissions.BasePermission):
    """
    Permission to check if user is at least an Operator.
    """

    def has_permission(self, request, view):
        return request.user.groups.filter(name__in=['Operator', 'Reviewer', 'Admin']).exists()


class IsReviewerOrAbove(permissions.BasePermission):
    """
    Permission to check if user is at least a Reviewer.
    """

    def has_permission(self, request, view):
        return request.user.groups.filter(name__in=['Reviewer', 'Admin']).exists()


class IsAdminUser(permissions.BasePermission):
    """
    Permission to check if user is an Admin.
    """

    def has_permission(self, request, view):
        return request.user.groups.filter(name='Admin').exists() or request.user.is_superuser
