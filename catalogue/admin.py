from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone

from .models import AccessRequest, AuditLog, CodePackage, Institution, PackageVersion


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ["name", "country"]
    search_fields = ["name"]


class PackageVersionInline(admin.TabularInline):
    model = PackageVersion
    extra = 0


@admin.register(CodePackage)
class CodePackageAdmin(admin.ModelAdmin):
    list_display = ["name", "is_restricted", "created_at"]
    list_filter = ["is_restricted"]
    search_fields = ["name"]
    inlines = [PackageVersionInline]


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = [
        "requester",
        "package_version",
        "institution",
        "status",
        "created_at",
    ]
    list_filter = ["status", "institution__country"]
    readonly_fields = ["status", "reviewed_by", "reviewed_at", "created_at"]
    actions = ["approve_requests", "reject_requests"]

    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None
        # Save the request and its audit entry together, or not at all.
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if is_new:
                AuditLog.objects.create(
                    actor=request.user,
                    action=AuditLog.Action.REQUEST_CREATED,
                    access_request=obj,
                    package_version=obj.package_version,
                )

    def _review(self, request, queryset, new_status, audit_action):
        total = queryset.count()
        reviewed = 0
        with transaction.atomic():
            pending = queryset.select_for_update().filter(
                status=AccessRequest.Status.PENDING
            )
            for access_request in pending:
                access_request.status = new_status
                access_request.reviewed_by = request.user
                access_request.reviewed_at = timezone.now()
                access_request.save()
                AuditLog.objects.create(
                    actor=request.user,
                    action=audit_action,
                    access_request=access_request,
                    package_version=access_request.package_version,
                    details={"new_status": new_status},
                )
                reviewed += 1

        if reviewed:
            self.message_user(request, f"{reviewed} request(s) marked {new_status}.")
        skipped = total - reviewed
        if skipped:
            self.message_user(
                request,
                f"{skipped} request(s) skipped because they were already reviewed.",
                level=messages.WARNING,
            )

    @admin.action(description="Approve selected pending requests")
    def approve_requests(self, request, queryset):
        self._review(
            request,
            queryset,
            AccessRequest.Status.APPROVED,
            AuditLog.Action.REQUEST_APPROVED,
        )

    @admin.action(description="Reject selected pending requests")
    def reject_requests(self, request, queryset):
        self._review(
            request,
            queryset,
            AccessRequest.Status.REJECTED,
            AuditLog.Action.REQUEST_REJECTED,
        )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "actor", "action", "access_request", "package_version"]
    list_filter = ["action"]

    # The audit log is read-only for everyone, including superusers.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
