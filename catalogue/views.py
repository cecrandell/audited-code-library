"""Views for the catalogue REST API.

Users can read the package catalogue, create access requests, see their
own requests, and download approved packages. Every request and every
download writes an audit entry.
"""

from django.db import transaction
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .models import AccessRequest, AuditLog, CodePackage
from .serializers import AccessRequestSerializer, CodePackageSerializer


class CodePackageViewSet(viewsets.ReadOnlyModelViewSet):
    # Load all versions in one query, to avoid one query per package.
    queryset = CodePackage.objects.prefetch_related("versions")
    serializer_class = CodePackageSerializer


# No update or destroy mixins: users cannot edit or delete requests.
class AccessRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = AccessRequestSerializer

    def get_queryset(self):
        # Users can only see their own requests. Every action, including
        # download, starts from this queryset, so other users' requests
        # return 404.
        return AccessRequest.objects.filter(requester=self.request.user).select_related(
            "requester", "package_version__package", "institution"
        )

    def perform_create(self, serializer):
        # Django REST Framework does not wrap views in a transaction, so save the request
        # and its audit entry together explicitly.
        with transaction.atomic():
            access_request = serializer.save(requester=self.request.user)
            AuditLog.objects.create(
                actor=self.request.user,
                action=AuditLog.Action.REQUEST_CREATED,
                access_request=access_request,
                package_version=access_request.package_version,
            )

    # POST, not GET: a download writes an audit entry, and GET requests
    # must not change state.
    @action(detail=True, methods=["post"], serializer_class=serializers.Serializer)
    def download(self, request, pk=None):
        access_request = self.get_object()
        if access_request.status != AccessRequest.Status.APPROVED:
            raise PermissionDenied("This request is not approved.")
        version = access_request.package_version
        AuditLog.objects.create(
            actor=request.user,
            action=AuditLog.Action.DOWNLOADED,
            access_request=access_request,
            package_version=version,
        )
        return Response(
            {
                "package": version.package.name,
                "version": version.version,
                "checksum_sha256": version.checksum_sha256,
            }
        )
