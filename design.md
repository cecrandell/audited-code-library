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

## Known Limitations

- **`catalogue/models.py`: bulk changes can bypass the audit log protection.** Django bulk operations, such as `AuditLog.objects.all().delete()` or `.update()`, skip the model methods. Raw SQL skips them too. The model methods stop accidental changes in the application.
- **`catalogue/models.py`: `is_restricted` is not enforced yet.** The database stores the flag, the admin shows it, and the API returns it, but the approval process does not check it.
- **`catalogue/admin.py`: edits are not logged.** The admin logs new packages and new versions, but not edits or deletions. For example, a change to a version's checksum creates no audit entry.
- **`catalogue/admin.py`: request details stay editable after a decision.** Staff can still change the requester, institution, version, or purpose of an approved request.
- **`catalogue/admin.py`: row locking needs PostgreSQL.** SQLite ignores `select_for_update()`, so the lock only works in production.

## Next Steps

- **`catalogue/models.py`: bulk changes can bypass the audit log protection.** In production, I would add database-level controls, for example a PostgreSQL trigger, or a database role with INSERT-only permission on the audit table.
- **`catalogue/models.py`: `is_restricted` is not enforced yet.** Only reviewers with a dedicated permission can approve restricted packages.
- **`catalogue/admin.py`: edits are not logged.** Log `formset.changed_objects` and `formset.deleted_objects`, make the checksum read-only after creation, and set `can_delete = False` on the version inline.
- **`catalogue/admin.py`: request details stay editable after a decision.** Make every field read-only once the request exists, with `get_readonly_fields`.
