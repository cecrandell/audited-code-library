"""Serializers for the catalogue REST API.

Every serializer lists its fields explicitly, so a new model field never
appears in the API by accident. Users can set only what they ask for and
why. The server sets who asked and what was decided.
"""

from rest_framework import serializers

from .models import AccessRequest, CodePackage, PackageVersion


class PackageVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageVersion
        fields = ["id", "version", "checksum_sha256", "released_at", "notes"]


class CodePackageSerializer(serializers.ModelSerializer):
    # Versions are visible in the package, but cannot be changed through
    # the API.
    versions = PackageVersionSerializer(many=True, read_only=True)

    class Meta:
        model = CodePackage
        fields = ["id", "name", "description", "is_restricted", "versions"]


class AccessRequestSerializer(serializers.ModelSerializer):
    # Set by the view from the logged-in user, never by the client.
    requester = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = AccessRequest
        # reviewed_by is not exposed.
        fields = [
            "id",
            "requester",
            "institution",
            "package_version",
            "purpose",
            "status",
            "reviewed_at",
            "created_at",
        ]
        # Users cannot set the outcome of their own request.
        read_only_fields = ["status", "reviewed_at", "created_at"]
