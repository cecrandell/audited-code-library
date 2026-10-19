from django.db import transaction
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .models import AccessRequest, AuditLog, CodePackage
from .serializers import AccessRequestSerializer, CodePackageSerializer


class CodePackageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CodePackage.objects.prefetch_related("versions")
    serializer_class = CodePackageSerializer


class AccessRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = AccessRequestSerializer

    def get_queryset(self):
        # Users can only see their own requests.
        return AccessRequest.objects.filter(requester=self.request.user).select_related(
            "package_version__package", "institution"
        )

    def perform_create(self, serializer):
        with transaction.atomic():
            access_request = serializer.save(requester=self.request.user)
            AuditLog.objects.create(
                actor=self.request.user,
                action=AuditLog.Action.REQUEST_CREATED,
                access_request=access_request,
                package_version=access_request.package_version,
            )

    @action(detail=True, methods=["post"])
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
