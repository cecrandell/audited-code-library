from django.conf import settings
from django.db import models
from django.db.models import Q


class Institution(models.Model):
    name = models.CharField(max_length=200, unique=True)
    country = models.CharField(
        max_length=2,
        help_text="ISO 3166-1 alpha-2 code, for example FR or US.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.country})"


class CodePackage(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_restricted = models.BooleanField(
        default=False,
        help_text="Needs extra review before release, for example export control.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PackageVersion(models.Model):
    package = models.ForeignKey(
        CodePackage, on_delete=models.PROTECT, related_name="versions"
    )
    version = models.CharField(max_length=50)
    checksum_sha256 = models.CharField(max_length=64)
    released_at = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["package__name", "-released_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["package", "version"], name="unique_package_version"
            )
        ]

    def __str__(self):
        return f"{self.package.name} {self.version}"


class AccessRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="access_requests",
    )
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    package_version = models.ForeignKey(
        PackageVersion, on_delete=models.PROTECT, related_name="access_requests"
    )
    purpose = models.TextField(help_text="Why the requester needs this software.")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"])]
        constraints = [
            # A request that is approved or rejected must record who reviewed it and when.
            models.CheckConstraint(
                condition=Q(status="pending")
                | Q(reviewed_by__isnull=False, reviewed_at__isnull=False),
                name="reviewed_request_has_reviewer",
            )
        ]

    def __str__(self):
        return f"{self.requester} -> {self.package_version} ({self.status})"


class AuditLog(models.Model):
    class Action(models.TextChoices):
        PACKAGE_ADDED = "package_added", "Package added"
        VERSION_ADDED = "version_added", "Version added"
        REQUEST_CREATED = "request_created", "Request created"
        REQUEST_APPROVED = "request_approved", "Request approved"
        REQUEST_REJECTED = "request_rejected", "Request rejected"
        DOWNLOADED = "downloaded", "Downloaded"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Empty if the system did the action.",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    access_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    package_version = models.ForeignKey(
        PackageVersion, on_delete=models.PROTECT, null=True, blank=True
    )
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("Audit log entries cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit log entries cannot be deleted.")

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.actor} {self.action}"
