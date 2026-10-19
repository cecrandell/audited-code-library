from rest_framework import serializers

from .models import AccessRequest, CodePackage, PackageVersion


class PackageVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageVersion
        fields = ["id", "version", "checksum_sha256", "released_at", "notes"]


class CodePackageSerializer(serializers.ModelSerializer):
    versions = PackageVersionSerializer(many=True, read_only=True)

    class Meta:
        model = CodePackage
        fields = ["id", "name", "description", "is_restricted", "versions"]


class AccessRequestSerializer(serializers.ModelSerializer):
    requester = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = AccessRequest
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
        read_only_fields = ["status", "reviewed_at", "created_at"]
