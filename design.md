# Design

## `catalogue/models.py`

**Summary:** The data model follows one request from start to finish. A user from an institution asks for a specific version of a code package and states the purpose. A reviewer approves or rejects it. Every step goes into an audit log. I put the important rules in the database itself. Versions are unique per package. An approved or rejected request must record who reviewed it and when. I use PROTECT on every foreign key, so history cannot disappear. Each version stores a SHA-256 checksum, so users can confirm the file is exactly what I released. The audit log is append-only at the model level. In production, I would also lock it at the database level.

**Key decisions:**

- The `CheckConstraint` on `AccessRequest` refuses a decision with no reviewer attached. Accountability lives in the data layer, below the application code.
- Users who leave are deactivated (`is_active = False`), never deleted, so their name stays on every action they took.
- A partial index covers only pending requests, because reviewers mostly search for those. `AuditLog.timestamp` is indexed for date-range audits.

## `catalogue/admin.py`

**Summary:** The admin is the staff interface. Staff add packages and versions, and review access requests. Every new package, new version, new request, and decision writes an audit log entry. Reviewers cannot edit a request's status directly. It changes only through the approve and reject actions. Those actions run in one database transaction and lock the selected rows, so a decision never exists without its audit entry, and two reviewers cannot decide the same request at the same time. Requests that were already reviewed are skipped, and the reviewer sees a warning. The audit log page is read-only for everyone, including superusers.

**Key decisions:**

- One helper, `_review`, holds the logic for both approve and reject, so the two paths cannot drift apart.
- Blocking delete permission on `AuditLog` also removes Django's bulk "Delete selected" action, which would bypass `AuditLog.delete()`.

## `catalogue/tests.py`

**Summary:** The tests check the rules that make the library trustworthy. There are 15 tests in four groups. The constraint tests prove that the database itself rejects a duplicate version and an approval with no reviewer. The audit log tests prove that an entry cannot be changed or deleted, and that adding a package in the admin writes audit entries. The review action tests run the real admin approve and reject actions, and prove that a request cannot be reviewed twice. The API tests prove that login is required, users see only their own requests, a pending request cannot be downloaded, and every successful download is logged. CI runs all tests against PostgreSQL on every push.

**Key decisions:**

- Tests use the real interfaces where possible: the admin pages through Django's test client, and the API through `APIClient`. They check what staff and users actually experience, not only the model methods.
- Tests check refusals as well as successes. For example, a pending download must return 403 and must also write no audit entry.
- Constraint tests wrap the failing save in `transaction.atomic()`. The savepoint keeps the test transaction usable after PostgreSQL raises the error.
- The API returns 404, not 403, for another user's request, so it does not reveal that the request exists. A test protects this behaviour.

## `catalogue/serializers.py`

**Summary:** The serializers translate between the database and the JSON API, and they decide what users can see and change. Package data is read-only: users see each package with its versions and checksums, but cannot change them. For access requests, a user sends only three things: the institution, the package version, and the purpose. The server sets everything else, including who asked, the status, and the review time. So a user cannot approve their own request, or make a request in someone else's name.

**Key decisions:**

- Every serializer lists its fields explicitly. This is an allowlist: a new model field never appears in the API by accident.
- `requester` is read-only and set by the server from the logged-in user.
- `status`, `reviewed_at`, and `created_at` are read-only, so the outcome of a request can only change through the admin review.
- `reviewed_by` is not exposed. Users see the decision and its time, but not which staff member made it.
- Versions are nested inside each package as read-only data, so one API call shows a package with all its releases.

## `catalogue/views.py`

**Summary:** The views are the API endpoints. Logged-in users can read the package catalogue, create an access request, see their own requests, and download a package once its request is approved. Users only ever see their own requests: every action starts from a queryset filtered by the logged-in user, so another user's request returns 404. Creating a request and writing its audit entry happen in one transaction. A download is refused with 403 unless the request is approved, and every successful download is logged with the checksum returned, so the user can verify the file.

**Key decisions:**

- The request endpoint is built only from the create, list, and retrieve mixins. Without update or destroy mixins, users cannot edit or delete a request.
- One filtered `get_queryset` protects every action, including download, so the privacy rule lives in one place.
- Download uses POST, not GET, because it writes an audit entry, and GET requests must not change state.
- `prefetch_related("versions")` loads all versions in one query, avoiding one query per package.
- `perform_create` uses an explicit transaction, because Django REST Framework does not wrap views in one by default.

## `config/urls.py` and `catalogue/urls.py`

**Summary:** The two URL files work as a pair. `config/urls.py` is the entry point for the whole project: it sends `/admin/` to the Django admin, `/api/` to the catalogue, and `/api-auth/` to the login pages for the browsable API. `catalogue/urls.py` uses a router, which creates one route for each action a ViewSet supports. So the routes always match the actions: the read-only package ViewSet gets list and detail routes, and the access request ViewSet also gets create and download routes.

**Key decisions:**

- A router generates the API routes, so a route cannot exist for an action the ViewSet does not support.
- Both ViewSets have an explicit `basename`. It is required for the access request ViewSet, which uses `get_queryset()`, and it keeps the route names consistent.

## `config/settings.py`

**Summary:** The settings read every environment-specific value from environment variables: the secret key, debug mode, allowed hosts, and database credentials. On a laptop, these come from a `.env` file that is not committed. A single variable, `USE_POSTGRES`, switches between PostgreSQL (Docker and continuous integration) and SQLite (local development). The API requires login by default, so every endpoint is protected unless a view sets its own rule.

**Key decisions:**

- Secure by default: the app does not start without a secret key, and debug mode is off unless explicitly turned on.
- All times are stored in UTC, so audit entries from different time zones stay in the correct order.

## Known Limitations

- **`catalogue/models.py`: bulk changes can bypass the audit log protection.** Django bulk operations, such as `AuditLog.objects.all().delete()` or `.update()`, skip the model methods. Raw SQL skips them too. The model methods stop accidental changes in the application.
- **`catalogue/models.py`: `is_restricted` is not enforced yet.** The database stores the flag, the admin shows it, and the API returns it, but the approval process does not check it.
- **`catalogue/admin.py`: edits are not logged.** The admin logs new packages and new versions, but not edits or deletions. For example, a change to a version's checksum creates no audit entry.
- **`catalogue/admin.py`: request details stay editable after a decision.** Staff can still change the requester, institution, version, or purpose of an approved request.
- **`catalogue/admin.py`: row locking needs PostgreSQL.** SQLite ignores `select_for_update()`, so the lock only works in production.
- **`catalogue/tests.py`: some rules have no test yet.** No test checks that the audit log admin is read-only, that non-staff users cannot use the admin actions, or that a user cannot download another user's approved request.
- **`catalogue/tests.py`: concurrent reviews are not tested.** The row locking in `_review` only matters when two reviewers act at the same moment, and a normal unit test runs one request at a time.
- **`catalogue/tests.py`: local test runs use SQLite.** Row locking and some constraint behaviour differ from PostgreSQL. CI uses PostgreSQL, so these differences only appear after a push.
- **`catalogue/serializers.py`: the institution is self-declared.** A user can choose any institution, and nothing checks that they work there. For export-controlled software, this is a real gap.
- **`catalogue/serializers.py`: every logged-in user sees every package.** This includes restricted packages and their checksums. Access is controlled at download, but for some export-controlled codes, even the list of what exists may be sensitive.
- **`catalogue/views.py`: download returns metadata, not a file.** The endpoint logs the download and returns the checksum, but no file is stored or delivered yet.
- **`catalogue/views.py`: approvals never expire.** An approved user can download as many times as they like, forever. Each download is logged, but nothing limits it.
- **`catalogue/views.py`: the request list runs one extra query per row.** The serializer shows the requester's name, but `requester` is not in `select_related`.
- **`catalogue/views.py`: lists are not paginated.** The package and request lists return every row at once.
- **`catalogue/tests.py`: tests hard-code API paths.** The API tests use paths like `/api/packages/`, so a change to the URL structure breaks them.
- **`config/urls.py`: the API has no version in its path.** A future change to the response format would affect every client at once.
- **`config/settings.py`: production security settings are not configured.** HTTPS redirects, secure cookies, and HTTP Strict Transport Security are not set, and there is no folder for collected static files, so the admin's styling would not load in production.

## Next Steps

- **`catalogue/models.py`: bulk changes can bypass the audit log protection.** In production, I would add database-level controls, for example a PostgreSQL trigger, or a database role with INSERT-only permission on the audit table.
- **`catalogue/models.py`: `is_restricted` is not enforced yet.** Only reviewers with a dedicated permission can approve restricted packages.
- **`catalogue/admin.py`: edits are not logged.** Log `formset.changed_objects` and `formset.deleted_objects`, make the checksum read-only after creation, and set `can_delete = False` on the version inline.
- **`catalogue/admin.py`: request details stay editable after a decision.** Make every field read-only once the request exists, with `get_readonly_fields`.
- **`catalogue/tests.py`: `is_restricted` has tests, but they are skipped.** `RestrictedPackageTests` describes the rule: a reviewer without the `approve_restricted` permission cannot approve a restricted package, and a reviewer with it can. When the rule is added to `AccessRequestAdmin._review`, remove the `@skip` decorator.
- **`catalogue/tests.py`: some rules have no test yet.** Add tests for the read-only audit log admin, non-staff access to admin actions, and downloads of another user's approved request.
- **`catalogue/tests.py`: concurrent reviews are not tested.** Add a `TransactionTestCase` that runs two reviews in parallel threads against PostgreSQL.
- **`catalogue/tests.py`: local test runs use SQLite.** Run the tests locally against PostgreSQL with `compose.yaml`, so local results match CI.
- **`catalogue/serializers.py`: the institution is self-declared.** Link each user to an institution (for example, a profile model), and have the server set the institution, as it does for the requester.
- **`catalogue/serializers.py`: every logged-in user sees every package.** Confirm the policy. If needed, filter restricted packages in the view, or hide their details from users without approved access.
- **`catalogue/tests.py`: tests hard-code API paths.** Build paths with `reverse()` and the router's route names, for example `reverse("package-list")`.
- **`config/urls.py`: the API has no version in its path.** Serve the API under `/api/v1/`, so a future version can run alongside it.
- **`config/settings.py`: production security settings are not configured.** Run `python manage.py check --deploy`, which lists every missing production setting, and add a production check to continuous integration. Set `STATIC_ROOT` and serve static files, for example with WhiteNoise.
