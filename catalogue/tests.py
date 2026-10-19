from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AccessRequest, AuditLog, CodePackage, Institution, PackageVersion

User = get_user_model()


class CatalogueTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            "admin", "admin@example.com", "test-password"
        )
        cls.user = User.objects.create_user(
            "researcher", "researcher@example.com", "test-password"
        )
        cls.institution = Institution.objects.create(
            name="Test University", country="FR"
        )
        cls.package = CodePackage.objects.create(name="DemoTransport")
        cls.version = PackageVersion.objects.create(
            package=cls.package,
            version="1.0",
            checksum_sha256="a" * 64,
            released_at=date(2026, 1, 1),
        )

    def make_request(self):
        return AccessRequest.objects.create(
            requester=self.user,
            institution=self.institution,
            package_version=self.version,
            purpose="Testing",
        )


class ConstraintTests(CatalogueTestCase):
    def test_package_cannot_have_duplicate_versions(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PackageVersion.objects.create(
                package=self.package,
                version="1.0",
                checksum_sha256="b" * 64,
                released_at=date(2026, 2, 1),
            )

    def test_approved_request_must_have_reviewer(self):
        access_request = self.make_request()
        access_request.status = AccessRequest.Status.APPROVED
        with self.assertRaises(IntegrityError), transaction.atomic():
            access_request.save()

    def test_approved_request_with_reviewer_saves(self):
        access_request = self.make_request()
        access_request.status = AccessRequest.Status.APPROVED
        access_request.reviewed_by = self.admin
        access_request.reviewed_at = timezone.now()
        access_request.save()
        access_request.refresh_from_db()
        self.assertEqual(access_request.status, AccessRequest.Status.APPROVED)


class AuditLogTests(CatalogueTestCase):
    def test_audit_entry_cannot_be_changed(self):
        entry = AuditLog.objects.create(
            actor=self.admin, action=AuditLog.Action.PACKAGE_ADDED
        )
        entry.action = AuditLog.Action.DOWNLOADED
        with self.assertRaises(ValueError):
            entry.save()

    def test_audit_entry_cannot_be_deleted(self):
        entry = AuditLog.objects.create(
            actor=self.admin, action=AuditLog.Action.PACKAGE_ADDED
        )
        with self.assertRaises(ValueError):
            entry.delete()

    def test_adding_package_in_admin_writes_audit_entries(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("admin:catalogue_codepackage_add"),
            {
                "name": "NewCode",
                "description": "",
                "versions-TOTAL_FORMS": "1",
                "versions-INITIAL_FORMS": "0",
                "versions-0-version": "2.0",
                "versions-0-checksum_sha256": "c" * 64,
                "versions-0-released_at": "2026-03-01",
                "versions-0-notes": "",
            },
        )
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.PACKAGE_ADDED).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.VERSION_ADDED).exists()
        )


class ReviewActionTests(CatalogueTestCase):
    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse("admin:catalogue_accessrequest_changelist")

    def run_action(self, action, access_request):
        return self.client.post(
            self.url,
            {"action": action, "index": 0, "_selected_action": [access_request.pk]},
        )

    def test_approve_sets_reviewer_and_writes_audit_entry(self):
        access_request = self.make_request()
        self.run_action("approve_requests", access_request)

        access_request.refresh_from_db()
        self.assertEqual(access_request.status, AccessRequest.Status.APPROVED)
        self.assertEqual(access_request.reviewed_by, self.admin)
        self.assertIsNotNone(access_request.reviewed_at)
        self.assertEqual(
            AuditLog.objects.filter(
                access_request=access_request,
                action=AuditLog.Action.REQUEST_APPROVED,
            ).count(),
            1,
        )

    def test_reject_writes_audit_entry(self):
        access_request = self.make_request()
        self.run_action("reject_requests", access_request)

        access_request.refresh_from_db()
        self.assertEqual(access_request.status, AccessRequest.Status.REJECTED)
        self.assertTrue(
            AuditLog.objects.filter(
                access_request=access_request,
                action=AuditLog.Action.REQUEST_REJECTED,
            ).exists()
        )

    def test_request_cannot_be_reviewed_twice(self):
        access_request = self.make_request()
        self.run_action("approve_requests", access_request)
        self.run_action("reject_requests", access_request)

        access_request.refresh_from_db()
        self.assertEqual(access_request.status, AccessRequest.Status.APPROVED)
        self.assertEqual(
            AuditLog.objects.filter(access_request=access_request).count(), 1
        )


class ApiTests(CatalogueTestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def approve(self, access_request):
        access_request.status = AccessRequest.Status.APPROVED
        access_request.reviewed_by = self.admin
        access_request.reviewed_at = timezone.now()
        access_request.save()

    def test_api_requires_login(self):
        response = APIClient().get("/api/packages/")
        self.assertIn(response.status_code, [401, 403])

    def test_list_packages(self):
        response = self.client.get("/api/packages/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["name"], "DemoTransport")

    def test_create_request_sets_requester_and_writes_audit_entry(self):
        response = self.client.post(
            "/api/requests/",
            {
                "institution": self.institution.pk,
                "package_version": self.version.pk,
                "purpose": "Research",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        access_request = AccessRequest.objects.get(pk=response.json()["id"])
        self.assertEqual(access_request.requester, self.user)
        self.assertTrue(
            AuditLog.objects.filter(
                access_request=access_request,
                action=AuditLog.Action.REQUEST_CREATED,
            ).exists()
        )

    def test_user_cannot_see_other_users_requests(self):
        other = User.objects.create_user("other", "other@example.com", "test-password")
        other_request = AccessRequest.objects.create(
            requester=other,
            institution=self.institution,
            package_version=self.version,
            purpose="Private",
        )
        response = self.client.get(f"/api/requests/{other_request.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_cannot_download_pending_request(self):
        access_request = self.make_request()
        response = self.client.post(f"/api/requests/{access_request.pk}/download/")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            AuditLog.objects.filter(action=AuditLog.Action.DOWNLOADED).exists()
        )

    def test_download_approved_request_writes_audit_entry(self):
        access_request = self.make_request()
        self.approve(access_request)
        response = self.client.post(f"/api/requests/{access_request.pk}/download/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checksum_sha256"], "a" * 64)
        self.assertTrue(
            AuditLog.objects.filter(
                access_request=access_request,
                action=AuditLog.Action.DOWNLOADED,
            ).exists()
        )
