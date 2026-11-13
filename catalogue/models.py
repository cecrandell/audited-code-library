"""Data model for the catalogue app.

Each class is a database table, and each field is a column.

Design rule: every foreign key uses on_delete=PROTECT. A record that other
records depend on cannot be deleted, so the history of who requested,
reviewed, and downloaded each package always stays complete.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q


class Institution(models.Model):
    """The organisation that a requester works for."""

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
    """A software package in the library, for example a simulation code."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    # Not enforced yet. The flag is stored, shown in the admin, and returned
    # by the API, but approval does not check it.
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
    """One release of a CodePackage."""

    package = models.ForeignKey(
        CodePackage,
        on_delete=models.PROTECT,
        related_name="versions",
    )
    version = models.CharField(max_length=50)
    # SHA-256 hash of the release file. Users compare it with their download
    # to confirm the file has not changed.
    checksum_sha256 = models.CharField(max_length=64)
    # The official release date, entered by staff. It can be earlier than
    # the date the version was added to the library.
    released_at = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        # Package name A to Z, then newest release first.
        ordering = [
            "package__name",
            "-released_at",
        ]
        constraints = [
            # Each package can have a given version number only once.
            models.UniqueConstraint(
                fields=["package", "version"], name="unique_package_version"
            )
        ]

    def __str__(self):
        return f"{self.package.name} {self.version}"


class AccessRequest(models.Model):
    """A request to use one PackageVersion.

    A request starts as pending. A reviewer then approves or rejects it.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    # requester and reviewed_by both point to the user table, so each needs
    # its own related_name.
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="access_requests",
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
    )
    package_version = models.ForeignKey(
        PackageVersion,
        on_delete=models.PROTECT,
        related_name="access_requests",
    )
    purpose = models.TextField(help_text="Why the requester needs this software.")
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    # Empty while the request is pending.
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_requests",
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # Partial index: reviewers mostly look for pending requests, and
            # most requests end up approved or rejected, so indexing only
            # pending rows keeps the index small.
            models.Index(
                fields=["status"],
                condition=Q(status="pending"),
                name="pending_requests_idx",
            )
        ]
        constraints = [
            # A request that is approved or rejected must record who
            # reviewed it and when. The database enforces this rule.
            models.CheckConstraint(
                condition=Q(status="pending")
                | Q(reviewed_by__isnull=False, reviewed_at__isnull=False),
                name="reviewed_request_has_reviewer",
            )
        ]

    def __str__(self):
        return f"{self.requester} -> {self.package_version} ({self.status})"


class AuditLog(models.Model):
    """An append-only record of every important action.

    save() blocks edits to existing entries, and delete() blocks removal.
    Bulk QuerySet operations (update, delete) and raw SQL bypass these
    methods, so a production system should also limit permissions on this
    table at the database level.
    """

    class Action(models.TextChoices):
        PACKAGE_ADDED = "package_added", "Package added"
        VERSION_ADDED = "version_added", "Version added"
        REQUEST_CREATED = "request_created", "Request created"
        REQUEST_APPROVED = "request_approved", "Request approved"
        REQUEST_REJECTED = "request_rejected", "Request rejected"
        DOWNLOADED = "downloaded", "Downloaded"

    # PROTECT keeps every actor on record. Deactivate users who leave;
    # do not delete them.
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
        PackageVersion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    # Extra context for each action, stored without changing the table design.
    details = models.JSONField(default=dict, blank=True)
    # Indexed because audits usually search by date range.
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        # A saved entry already has a primary key, so this blocks edits.
        if self.pk is not None:
            raise ValueError("Audit log entries cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit log entries cannot be deleted.")

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.actor} {self.action}"
